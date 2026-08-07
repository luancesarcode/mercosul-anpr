"""Tests for vehicle detection post-processing."""

from __future__ import annotations

from mercosul_anpr.vision.vehicle_detector import VehicleDetector


def test_overlapping_cross_class_vehicle_boxes_are_deduplicated() -> None:
    vehicles = [
        {"bbox": (10, 10, 200, 160), "conf": 0.95},
        {"bbox": (12, 12, 198, 158), "conf": 0.82},
        {"bbox": (230, 20, 390, 170), "conf": 0.80},
    ]

    deduplicated = VehicleDetector._deduplicate(vehicles)

    assert len(deduplicated) == 2
    assert deduplicated[0]["conf"] == 0.95
    assert deduplicated[1]["bbox"] == (230, 20, 390, 170)
