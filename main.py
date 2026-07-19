#!/usr/bin/env python3
"""Production-ready ANPR entrypoint.

This module keeps backward compatibility with manual path constants while
adding modular architecture, structured logging, ROI plate detection,
hybrid association, temporal vote stabilization, and optional profiling.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING

from core.config import AppConfig, load_app_config
from core.constants import PROJECT_ROOT
from core.logger import build_runtime_logger, close_logger
from core.profiling import enable_line_profiler, finalize_line_profiler, finish_cprofile, start_cprofile
from io_layer.result_writer import ResultWriter
from io_layer.video_reader import InputSourceReader
from render.exporter import OutputExporter

if TYPE_CHECKING:
    from pipeline.processor import PipelineProcessor


COCO_MODEL_PATH = PROJECT_ROOT / "modelos" / "yolov8n.pt"
PLATE_MODEL_PATH = PROJECT_ROOT / "modelos" / "best.pt"
RUNS_DIR = PROJECT_ROOT / "runs" / "predict"
CAMINHO_VIDEO_ENTRADA = PROJECT_ROOT / "Videos_input" / "Test1.mp4"
#CAMINHO_IMAGE_ENTRADA = PROJECT_ROOT / "Imagens_input" / "Test1.jpg"


def exigir_arquivo(path: Path, label: str) -> Path:
    """Validate that required file exists.

    Args:
        path: Candidate file path.
        label: Human-readable label for errors.

    Returns:
        Resolved absolute path.

    Raises:
        FileNotFoundError: When path does not exist.
    """
    if path.is_file():
        return path.resolve()
    raise FileNotFoundError(f"[erro] {label} nao encontrado: {path}")


def _resolve_manual_source() -> Path | None:
    if "CAMINHO_VIDEO_ENTRADA" in globals() and CAMINHO_VIDEO_ENTRADA is not None:
        return Path(CAMINHO_VIDEO_ENTRADA)
    if "CAMINHO_IMAGE_ENTRADA" in globals() and globals().get("CAMINHO_IMAGE_ENTRADA") is not None:
        return Path(globals()["CAMINHO_IMAGE_ENTRADA"])
    return None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ANPR pipeline (vehicle + plate + OCR).")
    parser.add_argument("source", nargs="?", help="Arquivo de entrada (imagem/video).")
    parser.add_argument("--coco-model", dest="coco_model", help="Modelo YOLO de veiculos.")
    parser.add_argument("--plate-model", dest="plate_model", help="Modelo YOLO de placas.")
    parser.add_argument("--runs-dir", dest="runs_dir", help="Diretorio de saida.")
    parser.add_argument("--profile", action="store_true", help="Ativa cProfile nesta execucao.")
    parser.add_argument(
        "--line-profile",
        action="store_true",
        help="Ativa line_profiler para process_frame, se instalado.",
    )
    return parser


def _load_config_from_args(args: argparse.Namespace) -> AppConfig:
    manual_source = _resolve_manual_source()
    source_path = args.source or manual_source
    overrides: dict[str, str | Path | None] = {
        "source_path": source_path,
        "coco_model_path": args.coco_model or COCO_MODEL_PATH,
        "plate_model_path": args.plate_model or PLATE_MODEL_PATH,
        "runs_dir": args.runs_dir or RUNS_DIR,
    }
    config = load_app_config(PROJECT_ROOT, overrides=overrides)
    return config


def _parse_live_source(raw_source: str | None) -> str | int | None:
    if raw_source is None:
        return None
    raw = raw_source.strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    low = raw.lower()
    if low.startswith(("rtsp://", "rtmp://", "http://", "https://")):
        return raw
    return None


def _resolve_runtime_source(
    config: AppConfig,
    args: argparse.Namespace,
) -> tuple[Path | str | int, str, Path]:
    live_source = _parse_live_source(args.source)
    if live_source is not None:
        if isinstance(live_source, int):
            output_ref = Path(f"live_{live_source}.mp4")
        else:
            output_ref = Path("live_stream.mp4")
        return live_source, str(live_source), output_ref

    source_file = exigir_arquivo(config.source_path, "Entrada")
    return source_file, str(source_file), source_file


def _format_result_line(frame_name: str, vehicles: list[dict[str, Any]], plates: list[dict[str, Any]]) -> tuple[str, str, float, int | None]:
    if not plates:
        line = f"[result] {frame_name} => N/A (vehicles={len(vehicles)}, plates={len(plates)})"
        return line, "N/A", 0.0, None

    best_plate = max(plates, key=lambda item: item.get("text_conf", 0.0))
    track_id = best_plate.get("vehicle_track_id")
    id_label = f"ID:{int(track_id):02d}" if track_id is not None else "ID:N/A"
    plate_text = str(best_plate.get("text") or "N/A")
    conf = float(best_plate.get("text_conf", 0.0))
    line = (
        f"[result] {frame_name} => {id_label} {plate_text} "
        f"(vehicles={len(vehicles)}, plates={len(plates)}, ocr={conf:.1f})"
    )
    return line, plate_text, conf, int(track_id) if track_id is not None else None


def _build_processor(config: AppConfig, device: str | int) -> PipelineProcessor:
    from pipeline.processor import PipelineProcessor
    from pipeline.temporal_voter import TemporalVoter
    from pipeline.tracker import IoUTracker
    from vision.ocr_engine import OCREngine
    from vision.plate_detector import PlateDetector
    from vision.vehicle_detector import VehicleDetector

    vehicle_detector = VehicleDetector(config.coco_model_path, config.detection, config.vehicle_classes)
    plate_detector = PlateDetector(
        config.plate_model_path,
        config.detection,
        roi_cache_ttl=config.association.roi_cache_ttl,
    )
    ocr_engine = OCREngine()
    ocr_engine.warmup()
    tracker = IoUTracker(config.tracking)
    voter = TemporalVoter(config.tracking)
    return PipelineProcessor(
        config=config,
        device=device,
        vehicle_detector=vehicle_detector,
        plate_detector=plate_detector,
        ocr_engine=ocr_engine,
        tracker=tracker,
        voter=voter,
    )


def _run_pipeline(config: AppConfig, args: argparse.Namespace) -> int:
    from vision.vehicle_detector import escolher_dispositivo

    source_input, source_display, source_output_ref = _resolve_runtime_source(config, args)
    coco_model = exigir_arquivo(config.coco_model_path, "Modelo COCO")
    plate_model = exigir_arquivo(config.plate_model_path, "Modelo de placa")

    device = escolher_dispositivo()
    logger = build_runtime_logger(config.logging)
    profiler = start_cprofile(config.profiling.enable_cprofile or args.profile)

    try:
        processor = _build_processor(config, device)
        line_profiler = enable_line_profiler(processor, config.profiling.enable_line_profiler or args.line_profile, config.runs_dir)
        with InputSourceReader(source_input, config.image_extensions) as reader:
            with OutputExporter(config.runs_dir, source_output_ref, reader.is_image, reader.fps) as exporter:
                with ResultWriter(exporter.output_path, logger) as writer:
                    _write_startup_lines(writer, source_display, coco_model, plate_model, device)
                    confirmar_imediato = reader.is_image
                    for packet in reader.frames():
                        processed = processor.process_frame(packet.frame, packet.frame_idx, confirmar_imediato)
                        exporter.write_frame(processed.annotated_frame)
                        frame_name = _resolve_frame_name(source_input, reader.is_image, packet.frame_idx)
                        result_line, plate_text, conf, track_id = _format_result_line(frame_name, processed.vehicles, processed.plates)
                        writer.write_line(result_line)
                        writer.log_frame_event(packet.frame_idx, len(processed.vehicles), plate_text, conf, track_id)
                        writer.log_profile_event(packet.frame_idx, processed.metrics.fps, processed.metrics.elapsed_ms)

                    writer.write_line(f"[info] output: {exporter.output_path.resolve()}")
                    writer.write_line(f"[info] log   : {writer.text_path.resolve()}")
        finalize_line_profiler(line_profiler)
    finally:
        finish_cprofile(profiler, config.runs_dir)
        close_logger(logger)
    return 0


def _write_startup_lines(
    writer: ResultWriter,
    source: Path | str | int,
    coco_model: Path,
    plate_model: Path,
    device: str | int,
) -> None:
    line_device = "[info] device : cpu" if device == "cpu" else "[info] device : cuda:0"
    writer.write_line(line_device)
    writer.write_line("[info] Iniciando pipeline simplificado")
    writer.write_line(f"[info] source    : {source}")
    writer.write_line(f"[info] coco model: {coco_model}")
    writer.write_line(f"[info] plate model: {plate_model}")


def _resolve_frame_name(source_input: Path | str | int, is_image: bool, frame_idx: int) -> str:
    if not is_image:
        return f"frame_{frame_idx:06d}"
    if isinstance(source_input, Path):
        return source_input.name
    return str(source_input)


def principal(argv: list[str] | None = None) -> int:
    """Application entrypoint.

    Args:
        argv: Optional command-line argument list.

    Returns:
        Process exit code.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        config = _load_config_from_args(args)
        return _run_pipeline(config, args)
    except (FileNotFoundError, NameError) as exc:
        print(exc, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[erro] Falha de execucao: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
