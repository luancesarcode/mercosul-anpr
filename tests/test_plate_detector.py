"""Tests for state-safe YOLO plate inference calls."""

from __future__ import annotations

from types import SimpleNamespace

from mercosul_anpr.core.config import DetectionConfig
from mercosul_anpr.vision.plate_detector import PlateDetector


class _FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [SimpleNamespace(boxes=None)]


def test_primary_inference_resets_augmentation_after_recall() -> None:
    detector = PlateDetector.__new__(PlateDetector)
    detector._model = _FakeModel()
    detector._cfg = DetectionConfig(640, 0.6, 0.7, 0.002, 0.01, 0.003, 0.5, 6)
    detector._roi_cache_ttl = 0
    detector._roi_cache = {}

    detector._predict_boxes(object(), "cpu")
    detector._predict_boxes(object(), "cpu")

    assert [call["augment"] for call in detector._model.calls] == [False, True, False, True]
