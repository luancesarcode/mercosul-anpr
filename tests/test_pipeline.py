"""Integration-like test for frame processor orchestration."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from mercosul_anpr.core.config import (
    AppConfig,
    AssociationConfig,
    DetectionConfig,
    DisplayConfig,
    LoggingConfig,
    ProfilingConfig,
    TrackingConfig,
)
from mercosul_anpr.pipeline.processor import PipelineProcessor
from mercosul_anpr.pipeline.temporal_voter import TemporalVoter
from mercosul_anpr.pipeline.tracker import IoUTracker
from mercosul_anpr.vision.ocr_engine import OCRResult


class _FakeVehicleDetector:
    def detect(self, frame, device):
        _ = (frame, device)
        return [{"bbox": (50, 20, 200, 160), "conf": 0.93}]


class _FakeVehicleDetectorEmpty:
    def detect(self, frame, device):
        _ = (frame, device)
        return []


class _FakeVehicleDetectorUnrelated:
    def detect(self, frame, device):
        _ = (frame, device)
        return [{"bbox": (5, 5, 60, 60), "conf": 0.93}]


class _FakePlateDetector:
    def detect_by_vehicle_rois(self, frame, vehicles, frame_idx, device):
        _ = (frame, vehicles, frame_idx, device)
        return [
            {
                "bbox": [90, 90, 150, 130],
                "det_conf": 0.88,
                "placa_recortada": np.zeros((20, 50, 3), dtype=np.uint8),
                "placa_recortada_processada": np.zeros((20, 50), dtype=np.uint8),
                "vehicle_track_id": 1,
            }
        ]

    def detect_global(self, frame, device):
        _ = (frame, device)
        return []


class _FakePlateDetectorGlobal(_FakePlateDetector):
    def detect_global(self, frame, device):
        _ = (frame, device)
        return [
            {
                "bbox": [90, 90, 150, 130],
                "det_conf": 0.88,
                "placa_recortada": np.zeros((20, 50, 3), dtype=np.uint8),
                "placa_recortada_processada": np.zeros((20, 50), dtype=np.uint8),
            }
        ]


class _FakePlateDetectorUnassociatedGlobal(_FakePlateDetectorGlobal):
    def detect_by_vehicle_rois(self, frame, vehicles, frame_idx, device):
        _ = (frame, vehicles, frame_idx, device)
        return []


class _FakePlateDetectorCropped(_FakePlateDetectorGlobal):
    def detect_global(self, frame, device):
        candidates = super().detect_global(frame, device)
        candidates[0]["bbox"] = [0, 60, 80, 170]
        candidates[0]["det_conf"] = 0.09
        return candidates

    def detect_cropped_plate(self, frame):
        _ = frame
        return [
            {
                "bbox": [5, 50, 295, 150],
                "det_conf": 0.60,
                "placa_recortada": np.zeros((100, 290, 3), dtype=np.uint8),
                "placa_recortada_processada": np.zeros((100, 290), dtype=np.uint8),
            }
        ]


class _FakeOcrEngine:
    def read_candidate(self, candidate):
        _ = candidate
        return OCRResult(text="PDH2164", score=94.0, pattern="LLLDDDD", det_conf=0.88)


class _FakeOcrEngineLowConf:
    def read_candidate(self, candidate):
        _ = candidate
        return OCRResult(text="PDH2164", score=45.0, pattern="LLLDDDD", det_conf=0.88)


def _build_config() -> AppConfig:
    project_root = Path(__file__).resolve().parent.parent
    return AppConfig(
        project_root=project_root,
        source_path=project_root / "Videos_input" / "Test1.mp4",
        coco_model_path=project_root / "modelos" / "yolov8n.pt",
        plate_model_path=project_root / "modelos" / "best.pt",
        runs_dir=project_root / "runs" / "predict",
        image_extensions={".jpg", ".png", ".mp4"},
        vehicle_classes=[2, 3, 5, 7],
        detection=DetectionConfig(640, 0.5, 0.7, 0.002, 0.01, 0.003, 0.5, 6),
        tracking=TrackingConfig(0.3, 1, 15, 10, 3, 30, 2, 65.0, 1),
        association=AssociationConfig(True, True, 0.2, (0.5, 0.3, 0.2), 2),
        display=DisplayConfig(70.0, 100.0, True, 0.35),
        logging=LoggingConfig(project_root / "runs" / "logs", "test.log", 500000, 2),
        profiling=ProfilingConfig(False, False),
    )


def test_processor_outputs_plate_and_metrics() -> None:
    config = _build_config()
    tracker = IoUTracker(config.tracking)
    voter = TemporalVoter(config.tracking)
    processor = PipelineProcessor(
        config=config,
        device="cpu",
        vehicle_detector=_FakeVehicleDetector(),
        plate_detector=_FakePlateDetector(),
        ocr_engine=_FakeOcrEngine(),
        tracker=tracker,
        voter=voter,
    )

    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    result = processor.process_frame(frame, frame_idx=1, confirmar_veiculo_imediato=True)

    assert result.frame_idx == 1
    assert len(result.vehicles) == 1
    assert len(result.plates) == 1
    assert result.plates[0]["text"] == "PDH2164"
    assert result.metrics.elapsed_ms > 0
    assert result.metrics.fps > 0


def test_processor_hides_plate_below_confidence_interval() -> None:
    config = _build_config()
    tracker = IoUTracker(config.tracking)
    voter = TemporalVoter(config.tracking)
    processor = PipelineProcessor(
        config=config,
        device="cpu",
        vehicle_detector=_FakeVehicleDetector(),
        plate_detector=_FakePlateDetector(),
        ocr_engine=_FakeOcrEngineLowConf(),
        tracker=tracker,
        voter=voter,
    )

    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    result = processor.process_frame(frame, frame_idx=1, confirmar_veiculo_imediato=True)

    assert len(result.vehicles) == 1
    assert len(result.plates) == 0


def test_processor_accepts_global_plate_without_vehicle() -> None:
    config = _build_config()
    processor = PipelineProcessor(
        config=config,
        device="cpu",
        vehicle_detector=_FakeVehicleDetectorEmpty(),
        plate_detector=_FakePlateDetectorGlobal(),
        ocr_engine=_FakeOcrEngine(),
        tracker=IoUTracker(config.tracking),
        voter=TemporalVoter(config.tracking),
    )

    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    result = processor.process_frame(frame, frame_idx=1, confirmar_veiculo_imediato=True)

    assert result.vehicles == []
    assert result.plates[0]["text"] == "PDH2164"
    assert result.plates[0]["vehicle_track_id"] is None


def test_processor_keeps_valid_global_plate_when_detected_vehicle_is_unrelated() -> None:
    config = _build_config()
    processor = PipelineProcessor(
        config=config,
        device="cpu",
        vehicle_detector=_FakeVehicleDetectorUnrelated(),
        plate_detector=_FakePlateDetectorUnassociatedGlobal(),
        ocr_engine=_FakeOcrEngine(),
        tracker=IoUTracker(config.tracking),
        voter=TemporalVoter(config.tracking),
    )

    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    result = processor.process_frame(frame, frame_idx=1, confirmar_veiculo_imediato=True)

    assert result.plates[0]["text"] == "PDH2164"
    assert result.plates[0]["vehicle_track_id"] is None


def test_processor_prefers_isolated_plate_crop_over_partial_global_detection() -> None:
    config = _build_config()
    processor = PipelineProcessor(
        config=config,
        device="cpu",
        vehicle_detector=_FakeVehicleDetectorEmpty(),
        plate_detector=_FakePlateDetectorCropped(),
        ocr_engine=_FakeOcrEngine(),
        tracker=IoUTracker(config.tracking),
        voter=TemporalVoter(config.tracking),
    )

    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    result = processor.process_frame(frame, frame_idx=1, confirmar_veiculo_imediato=True)

    assert result.plates[0]["bbox"] == [5, 50, 295, 150]
    assert result.plates[0]["det_conf"] == 0.88


def test_processor_reuses_stable_ocr_when_interval_skips_new_ocr() -> None:
    config = _build_config()
    config = AppConfig(
        project_root=config.project_root,
        source_path=config.source_path,
        coco_model_path=config.coco_model_path,
        plate_model_path=config.plate_model_path,
        runs_dir=config.runs_dir,
        image_extensions=config.image_extensions,
        vehicle_classes=config.vehicle_classes,
        detection=config.detection,
        tracking=TrackingConfig(
            config.tracking.track_iou,
            config.tracking.track_min_hits,
            config.tracking.track_max_age,
            config.tracking.plate_vote_window,
            config.tracking.plate_switch_dominance_frames,
            config.tracking.debugger_window_frames,
            config.tracking.plate_min_occurrences,
            config.tracking.plate_min_score,
            2,
        ),
        association=config.association,
        display=config.display,
        logging=config.logging,
        profiling=config.profiling,
    )
    tracker = IoUTracker(config.tracking)
    voter = TemporalVoter(config.tracking)
    ocr = _FakeOcrEngine()
    processor = PipelineProcessor(
        config=config,
        device="cpu",
        vehicle_detector=_FakeVehicleDetector(),
        plate_detector=_FakePlateDetector(),
        ocr_engine=ocr,
        tracker=tracker,
        voter=voter,
    )
    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    r1 = processor.process_frame(frame, frame_idx=1, confirmar_veiculo_imediato=True)
    r2 = processor.process_frame(frame, frame_idx=2, confirmar_veiculo_imediato=True)

    assert len(r1.plates) == 1
    assert len(r2.plates) == 1
    assert r2.plates[0]["text"] == "PDH2164"
