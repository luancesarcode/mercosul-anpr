"""Frame processing orchestration for the ANPR pipeline."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from mercosul_anpr.core.config import AppConfig
from mercosul_anpr.pipeline.associator import associar_placa_ao_veiculo
from mercosul_anpr.pipeline.temporal_voter import TemporalVoter
from mercosul_anpr.pipeline.tracker import IoUTracker, iou_caixas
from mercosul_anpr.render.overlay import desenhar_anotacoes, desenhar_debugger_superior_esquerda
from mercosul_anpr.vision.ocr_engine import OCREngine
from mercosul_anpr.vision.plate_detector import PlateDetector
from mercosul_anpr.vision.vehicle_detector import VehicleDetector


@dataclass(frozen=True)
class FrameMetrics:
    """Per-frame performance metrics."""

    frame_idx: int
    elapsed_ms: float
    fps: float
    stage_ms: dict[str, float]


@dataclass(frozen=True)
class ProcessedFrame:
    """Processed frame payload."""

    frame_idx: int
    annotated_frame: Any
    vehicles: list[dict[str, Any]]
    plates: list[dict[str, Any]]
    metrics: FrameMetrics


class PipelineProcessor:
    """Main frame-level processing pipeline."""

    def __init__(
        self,
        config: AppConfig,
        device: str | int,
        vehicle_detector: VehicleDetector,
        plate_detector: PlateDetector,
        ocr_engine: OCREngine,
        tracker: IoUTracker,
        voter: TemporalVoter,
    ) -> None:
        self.config = config
        self.device = device
        self.vehicle_detector = vehicle_detector
        self.plate_detector = plate_detector
        self.ocr_engine = ocr_engine
        self.tracker = tracker
        self.voter = voter
        self._plate_bbox_state: dict[int, dict[str, Any]] = {}
        self._last_ocr_frame: dict[int, int] = {}

    def process_frame(self, frame: Any, frame_idx: int, confirmar_veiculo_imediato: bool) -> ProcessedFrame:
        """Process one frame end-to-end and return render + metadata."""
        marks = {"total": time.perf_counter()}

        marks["vehicle_start"] = time.perf_counter()
        vehicles = self.vehicle_detector.detect(frame, self.device)
        vehicles = self.tracker.update(vehicles, frame_idx)
        vehicles_for_use = self._select_vehicles_for_use(vehicles, confirmar_veiculo_imediato)
        marks["vehicle_end"] = time.perf_counter()

        self.voter.cleanup(self.tracker.active_ids(), frame_idx)
        self._cleanup_bbox_state(self.tracker.active_ids(), frame_idx)

        marks["plate_start"] = time.perf_counter()
        candidates = self._detect_plate_candidates(
            frame,
            vehicles_for_use,
            frame_idx,
            include_global=confirmar_veiculo_imediato,
        )
        plates = self._resolve_plate_predictions(frame, frame_idx, candidates, vehicles_for_use)
        marks["plate_end"] = time.perf_counter()

        marks["render_start"] = time.perf_counter()
        self.voter.update_debugger(plates, frame_idx)
        annotated = desenhar_anotacoes(frame, vehicles_for_use, plates)
        annotated = desenhar_debugger_superior_esquerda(annotated, self.voter.debugger_lines())
        marks["render_end"] = time.perf_counter()

        metrics = self._build_metrics(frame_idx, marks)
        return ProcessedFrame(frame_idx, annotated, vehicles_for_use, plates, metrics)

    def _select_vehicles_for_use(
        self,
        vehicles: list[dict[str, Any]],
        confirmar_veiculo_imediato: bool,
    ) -> list[dict[str, Any]]:
        if confirmar_veiculo_imediato:
            return vehicles
        return [vehicle for vehicle in vehicles if vehicle.get("confirmed", False)]

    def _detect_plate_candidates(
        self,
        frame: Any,
        vehicles: list[dict[str, Any]],
        frame_idx: int,
        *,
        include_global: bool,
    ) -> list[dict[str, Any]]:
        use_roi = self.config.association.use_roi_detection and bool(vehicles)
        roi_candidates: list[dict[str, Any]] = []
        if use_roi:
            roi_candidates = self.plate_detector.detect_by_vehicle_rois(frame, vehicles, frame_idx, self.device)
            if roi_candidates and not include_global:
                return roi_candidates
        candidates = self.plate_detector.detect_global(frame, self.device)
        if roi_candidates:
            candidates = self._deduplicate_plate_candidates([*roi_candidates, *candidates])
        if vehicles:
            return candidates
        detect_cropped_plate = getattr(self.plate_detector, "detect_cropped_plate", None)
        if callable(detect_cropped_plate):
            fallback = detect_cropped_plate(frame)
            if fallback:
                return fallback
        return candidates

    @staticmethod
    def _deduplicate_plate_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.get("vehicle_track_id") is not None,
                float(item.get("det_conf", 0.0)),
            ),
            reverse=True,
        )
        kept: list[dict[str, Any]] = []
        for candidate in ordered:
            bbox = candidate.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            bbox_tuple = tuple(int(value) for value in bbox)
            if any(iou_caixas(bbox_tuple, tuple(int(value) for value in item["bbox"])) >= 0.60 for item in kept):
                continue
            kept.append(candidate)
        return kept

    def _resolve_plate_predictions(
        self,
        frame: Any,
        frame_idx: int,
        candidates: list[dict[str, Any]],
        vehicles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        height, width = frame.shape[:2]
        plates: list[dict[str, Any]] = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            bbox = self._clamp_bbox(candidate.get("bbox"), width, height)
            if bbox is None:
                continue

            vehicle_idx = self._resolve_vehicle_index(candidate, bbox, vehicles)
            track_id = int(vehicles[vehicle_idx].get("track_id")) if vehicle_idx is not None else None
            det_conf = float(candidate.get("det_conf", 0.0))
            voted_text, voted_score, voted_pattern, det_conf = self._get_voted_ocr_for_track(
                track_id=track_id,
                candidate=candidate,
                frame_idx=frame_idx,
                det_conf=det_conf,
            )
            if not self._should_display_plate(voted_text, float(voted_score), voted_pattern):
                continue
            smoothed_bbox = self._smooth_bbox(track_id, bbox, frame_idx) if track_id is not None else bbox
            plates.append(
                {
                    "bbox": [smoothed_bbox[0], smoothed_bbox[1], smoothed_bbox[2], smoothed_bbox[3]],
                    "det_conf": det_conf,
                    "text": voted_text or "N/A",
                    "text_conf": float(voted_score),
                    "text_pattern": voted_pattern,
                    "vehicle_track_id": track_id,
                }
            )
        return plates

    def _get_voted_ocr_for_track(
        self,
        track_id: int | None,
        candidate: dict[str, Any],
        frame_idx: int,
        det_conf: float,
    ) -> tuple[str, float, str | None, float]:
        if track_id is not None and not self._should_run_ocr(track_id, frame_idx):
            stable_text, stable_score, stable_pattern = self.voter.get_stable_prediction(track_id)
            if stable_text:
                return stable_text, stable_score, stable_pattern, det_conf

        ocr = self.ocr_engine.read_candidate(candidate)
        voted_text, voted_score, voted_pattern = self.voter.vote(
            track_id=track_id,
            text=ocr.text,
            score=ocr.score,
            pattern=ocr.pattern,
            frame_idx=frame_idx,
        )
        if track_id is not None:
            self._last_ocr_frame[track_id] = frame_idx
        return voted_text, voted_score, voted_pattern, float(ocr.det_conf)

    def _should_run_ocr(self, track_id: int, frame_idx: int) -> bool:
        interval = max(1, int(self.config.tracking.ocr_interval_frames))
        if interval <= 1:
            return True
        last_frame = self._last_ocr_frame.get(track_id)
        if last_frame is None:
            return True
        return (frame_idx - last_frame) >= interval

    def _resolve_vehicle_index(
        self,
        candidate: dict[str, Any],
        bbox: tuple[int, int, int, int],
        vehicles: list[dict[str, Any]],
    ) -> int | None:
        linked_track = candidate.get("vehicle_track_id")
        if linked_track is not None:
            for idx, vehicle in enumerate(vehicles):
                if int(vehicle.get("track_id", -1)) == int(linked_track):
                    return idx
        return associar_placa_ao_veiculo(bbox, vehicles, self.config.association)

    def _clamp_bbox(
        self,
        bbox_raw: Any,
        frame_width: int,
        frame_height: int,
    ) -> tuple[int, int, int, int] | None:
        if not bbox_raw or len(bbox_raw) != 4:
            return None
        x1, y1, x2, y2 = [int(v) for v in bbox_raw]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = max(x1 + 1, min(frame_width - 1, x2))
        y2 = max(y1 + 1, min(frame_height - 1, y2))
        return x1, y1, x2, y2

    def _should_display_plate(self, text: str, score: float, pattern: str | None) -> bool:
        normalized_text = str(text or "").strip().upper()
        if not normalized_text or normalized_text == "N/A":
            return False
        if pattern is None:
            return False
        conf_min = self.config.display.plate_text_conf_min
        conf_max = self.config.display.plate_text_conf_max
        return conf_min <= float(score) <= conf_max

    def _smooth_bbox(
        self,
        track_id: int,
        bbox: tuple[int, int, int, int],
        frame_idx: int,
    ) -> tuple[int, int, int, int]:
        if not self.config.display.plate_bbox_smooth_enabled:
            return bbox
        alpha = float(self.config.display.plate_bbox_smooth_alpha)
        current = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        state = self._plate_bbox_state.get(track_id)
        if not isinstance(state, dict):
            self._plate_bbox_state[track_id] = {"bbox": current, "last_frame": frame_idx}
            return bbox

        previous = [float(v) for v in state.get("bbox", current)]
        smoothed = [((1.0 - alpha) * previous[i]) + (alpha * current[i]) for i in range(4)]
        state["bbox"] = smoothed
        state["last_frame"] = frame_idx
        return tuple(int(round(v)) for v in smoothed)  # type: ignore[return-value]

    def _cleanup_bbox_state(self, active_track_ids: set[int], frame_idx: int) -> None:
        stale_ids: list[int] = []
        for track_id, state in self._plate_bbox_state.items():
            if track_id in active_track_ids:
                continue
            last_frame = int(state.get("last_frame", -1)) if isinstance(state, dict) else -1
            if (frame_idx - last_frame) > self.config.tracking.track_max_age:
                stale_ids.append(track_id)
        for track_id in stale_ids:
            self._plate_bbox_state.pop(track_id, None)
            self._last_ocr_frame.pop(track_id, None)

    def _build_metrics(self, frame_idx: int, marks: dict[str, float]) -> FrameMetrics:
        total_ms = (time.perf_counter() - marks["total"]) * 1000.0
        fps = 1000.0 / total_ms if total_ms > 1e-6 else 0.0
        stages = {
            "vehicle": (marks["vehicle_end"] - marks["vehicle_start"]) * 1000.0,
            "plate_ocr": (marks["plate_end"] - marks["plate_start"]) * 1000.0,
            "render": (marks["render_end"] - marks["render_start"]) * 1000.0,
        }
        return FrameMetrics(frame_idx=frame_idx, elapsed_ms=total_ms, fps=fps, stage_ms=stages)
