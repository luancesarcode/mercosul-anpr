"""Use-case orchestration independent from CLI and HTTP."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mercosul_anpr.core.config import AppConfig
from mercosul_anpr.core.logger import build_runtime_logger, close_logger
from mercosul_anpr.core.profiling import (
    enable_line_profiler as start_line_profiler,
)
from mercosul_anpr.core.profiling import finalize_line_profiler, finish_cprofile, start_cprofile
from mercosul_anpr.domain.results import FrameResult, PlateObservation, ProcessingResult, consolidate_vehicles
from mercosul_anpr.io_layer.result_writer import ResultWriter
from mercosul_anpr.io_layer.structured_writer import StructuredResultWriter
from mercosul_anpr.io_layer.video_reader import InputSourceReader
from mercosul_anpr.render.exporter import OutputExporter

if TYPE_CHECKING:
    from mercosul_anpr.pipeline.processor import PipelineProcessor
    from mercosul_anpr.vision.ocr_engine import OCREngine
    from mercosul_anpr.vision.plate_detector import PlateDetector
    from mercosul_anpr.vision.vehicle_detector import VehicleDetector

ProgressCallback = Callable[[int, int | None], None]


class ProcessingService:
    """Execute one ANPR source and produce stable artifacts."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._run_lock = threading.Lock()
        self._device: str | int | None = None
        self._vehicle_detector: VehicleDetector | None = None
        self._plate_detector: PlateDetector | None = None
        self._ocr_engine: OCREngine | None = None

    def process(
        self,
        source: Path | str | int,
        *,
        output_dir: Path | None = None,
        run_id: str | None = None,
        progress: ProgressCallback | None = None,
        enable_cprofile: bool = False,
        enable_line_profiler: bool = False,
    ) -> ProcessingResult:
        """Process a source synchronously; callers may run it in a worker thread."""
        with self._run_lock:
            return self._process_locked(
                source,
                output_dir=output_dir,
                run_id=run_id,
                progress=progress,
                enable_cprofile=enable_cprofile,
                enable_line_profiler=enable_line_profiler,
            )

    def create_realtime_processor(self) -> PipelineProcessor:
        """Create stateful frame processing while reusing loaded inference models."""
        with self._run_lock:
            self._require_file(self.config.coco_model_path, "Modelo COCO")
            self._require_file(self.config.plate_model_path, "Modelo de placa")
            return self._build_processor(self.config)

    def process_realtime_frame(
        self,
        processor: PipelineProcessor,
        frame: Any,
        frame_idx: int,
    ) -> Any:
        """Process one camera frame without persisting it to disk."""
        if frame is None or getattr(frame, "size", 0) == 0:
            raise ValueError("Frame da câmera está vazio.")
        with self._run_lock:
            return processor.process_frame(frame, max(1, int(frame_idx)), confirmar_veiculo_imediato=False)

    def _process_locked(
        self,
        source: Path | str | int,
        *,
        output_dir: Path | None,
        run_id: str | None,
        progress: ProgressCallback | None,
        enable_cprofile: bool,
        enable_line_profiler: bool,
    ) -> ProcessingResult:
        source_input, source_display, output_ref = self._resolve_source(source)
        runtime_config = replace(self.config, runs_dir=(output_dir or self.config.runs_dir).resolve())
        runtime_config.runs_dir.mkdir(parents=True, exist_ok=True)
        self._require_file(runtime_config.coco_model_path, "Modelo COCO")
        self._require_file(runtime_config.plate_model_path, "Modelo de placa")

        processor = self._build_processor(runtime_config)
        logger = build_runtime_logger(runtime_config.logging)
        profiler = start_cprofile(runtime_config.profiling.enable_cprofile or enable_cprofile)
        run_token = run_id or uuid.uuid4().hex[:12]
        started_at = datetime.now(timezone.utc)
        started_clock = time.perf_counter()
        frame_results: list[FrameResult] = []

        try:
            line_profiler = start_line_profiler(
                processor,
                runtime_config.profiling.enable_line_profiler or enable_line_profiler,
                runtime_config.runs_dir,
            )
            with InputSourceReader(source_input, runtime_config.image_extensions) as reader:
                if progress:
                    progress(0, reader.total_frames)
                with OutputExporter(runtime_config.runs_dir, output_ref, reader.is_image, reader.fps) as exporter:
                    with ResultWriter(exporter.output_path, logger) as writer:
                        self._write_startup(writer, source_display, self._device)
                        for packet in reader.frames():
                            processed = processor.process_frame(packet.frame, packet.frame_idx, reader.is_image)
                            exporter.write_frame(processed.annotated_frame)
                            frame_name = output_ref.name if reader.is_image else f"frame_{packet.frame_idx:06d}"
                            line, plate_text, confidence, track_id = self._format_result_line(
                                frame_name,
                                processed.vehicles,
                                processed.plates,
                            )
                            writer.write_line(line)
                            writer.log_frame_event(
                                packet.frame_idx,
                                len(processed.vehicles),
                                plate_text,
                                confidence,
                                track_id,
                            )
                            writer.log_profile_event(
                                packet.frame_idx,
                                processed.metrics.fps,
                                processed.metrics.elapsed_ms,
                            )
                            frame_results.append(self._frame_result(processed))
                            if progress:
                                progress(packet.frame_idx, reader.total_frames)

                        completed_at = datetime.now(timezone.utc)
                        result = ProcessingResult(
                            run_id=run_token,
                            source=source_display,
                            source_type="image" if reader.is_image else "video_or_stream",
                            status="completed",
                            started_at=started_at.isoformat(),
                            completed_at=completed_at.isoformat(),
                            duration_ms=round((time.perf_counter() - started_clock) * 1000.0, 2),
                            frames_processed=len(frame_results),
                            frames=frame_results,
                            vehicles=consolidate_vehicles(frame_results),
                            artifacts={
                                "media": exporter.output_path.name,
                                "text": writer.text_path.name,
                            },
                        )
                        json_path, csv_path = StructuredResultWriter(exporter.output_path).write(result)
                        writer.write_line(f"[info] output: {exporter.output_path.resolve()}")
                        writer.write_line(f"[info] json  : {json_path.resolve()}")
                        writer.write_line(f"[info] csv   : {csv_path.resolve()}")
            finalize_line_profiler(line_profiler)
            return result
        finally:
            finish_cprofile(profiler, runtime_config.runs_dir)
            close_logger(logger)

    def _build_processor(self, config: AppConfig) -> PipelineProcessor:
        from mercosul_anpr.pipeline.processor import PipelineProcessor
        from mercosul_anpr.pipeline.temporal_voter import TemporalVoter
        from mercosul_anpr.pipeline.tracker import IoUTracker
        from mercosul_anpr.vision.ocr_engine import OCREngine
        from mercosul_anpr.vision.plate_detector import PlateDetector
        from mercosul_anpr.vision.vehicle_detector import VehicleDetector, escolher_dispositivo

        if self._device is None:
            self._device = escolher_dispositivo()
        if self._vehicle_detector is None:
            self._vehicle_detector = VehicleDetector(config.coco_model_path, config.detection, config.vehicle_classes)
        if self._plate_detector is None:
            self._plate_detector = PlateDetector(
                config.plate_model_path,
                config.detection,
                roi_cache_ttl=config.association.roi_cache_ttl,
            )
        else:
            self._plate_detector.reset()
        if self._ocr_engine is None:
            self._ocr_engine = OCREngine()
            self._ocr_engine.warmup()

        return PipelineProcessor(
            config=config,
            device=self._device,
            vehicle_detector=self._vehicle_detector,
            plate_detector=self._plate_detector,
            ocr_engine=self._ocr_engine,
            tracker=IoUTracker(config.tracking),
            voter=TemporalVoter(config.tracking),
        )

    def _resolve_source(self, source: Path | str | int) -> tuple[Path | str | int, str, Path]:
        if isinstance(source, int):
            return source, str(source), Path(f"live_{source}.mp4")
        if isinstance(source, str):
            raw = source.strip()
            if raw.isdigit():
                return int(raw), raw, Path(f"live_{raw}.mp4")
            if raw.lower().startswith(("rtsp://", "rtmp://", "http://", "https://")):
                return raw, raw, Path("live_stream.mp4")
            source = Path(raw)
        source_path = self._require_file(Path(source), "Entrada")
        return source_path, str(source_path), source_path

    @staticmethod
    def _require_file(path: Path, label: str) -> Path:
        if path.is_file():
            return path.resolve()
        raise FileNotFoundError(f"[erro] {label} nao encontrado: {path}")

    @staticmethod
    def _format_result_line(
        frame_name: str,
        vehicles: list[dict[str, Any]],
        plates: list[dict[str, Any]],
    ) -> tuple[str, str, float, int | None]:
        if not plates:
            return f"[result] {frame_name} => N/A (vehicles={len(vehicles)}, plates=0)", "N/A", 0.0, None
        best = max(plates, key=lambda item: item.get("text_conf", 0.0))
        track_id = best.get("vehicle_track_id")
        track_value = int(track_id) if track_id is not None else None
        id_label = f"ID:{track_value:02d}" if track_value is not None else "ID:N/A"
        text = str(best.get("text") or "N/A")
        confidence = float(best.get("text_conf", 0.0))
        line = (
            f"[result] {frame_name} => {id_label} {text} "
            f"(vehicles={len(vehicles)}, plates={len(plates)}, ocr={confidence:.1f})"
        )
        return line, text, confidence, track_value

    @staticmethod
    def _frame_result(processed: Any) -> FrameResult:
        plates = [
            PlateObservation(
                frame=processed.frame_idx,
                track_id=int(item["vehicle_track_id"]) if item.get("vehicle_track_id") is not None else None,
                text=str(item.get("text") or "N/A"),
                confidence=round(float(item.get("text_conf", 0.0)), 2),
                pattern=item.get("text_pattern"),
                detection_confidence=round(float(item.get("det_conf", 0.0)), 4),
                bbox=[int(value) for value in item.get("bbox", [])],
            )
            for item in processed.plates
        ]
        return FrameResult(
            frame=processed.frame_idx,
            vehicles=len(processed.vehicles),
            elapsed_ms=round(processed.metrics.elapsed_ms, 2),
            fps=round(processed.metrics.fps, 2),
            plates=plates,
        )

    @staticmethod
    def _write_startup(writer: ResultWriter, source: str, device: str | int | None) -> None:
        writer.write_line(f"[info] device : {'cpu' if device == 'cpu' else 'cuda:0'}")
        writer.write_line(f"[info] source : {source}")
