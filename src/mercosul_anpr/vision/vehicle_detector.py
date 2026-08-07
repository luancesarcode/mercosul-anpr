"""Vehicle detection module powered by YOLO."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ultralytics import YOLO

from mercosul_anpr.core.config import DetectionConfig


def escolher_dispositivo() -> str | int:
    """Select CUDA device when available, otherwise CPU."""
    try:
        import torch
    except Exception:
        return "cpu"

    if torch.cuda.is_available():
        return 0
    return "cpu"


class VehicleDetector:
    """YOLO-based detector for vehicles."""

    def __init__(
        self,
        model_path: Path,
        detection_config: DetectionConfig,
        vehicle_classes: list[int],
    ) -> None:
        self._model = YOLO(str(model_path))
        self._cfg = detection_config
        self._classes = vehicle_classes

    def detect(self, frame: Any, device: str | int) -> list[dict[str, Any]]:
        """Run vehicle inference and return filtered detections."""
        result = self._model.predict(
            source=frame,
            conf=self._cfg.vehicle_conf,
            iou=self._cfg.vehicle_iou,
            imgsz=self._cfg.img_size,
            device=device,
            classes=self._classes,
            agnostic_nms=True,
            augment=False,
            verbose=False,
        )
        prediction = result[0] if result else None
        return self._extract_vehicles(prediction, frame.shape[:2])

    def _extract_vehicles(self, result: Any, frame_shape: tuple[int, int]) -> list[dict[str, Any]]:
        vehicles: list[dict[str, Any]] = []
        if result is None or result.boxes is None or len(result.boxes) == 0:
            return vehicles

        height, width = frame_shape
        frame_area = max(1, height * width)

        for i in range(len(result.boxes)):
            conf = float(result.boxes.conf[i]) if result.boxes.conf is not None else 0.0
            if conf < self._cfg.vehicle_conf:
                continue
            x1, y1, x2, y2 = [int(v) for v in result.boxes.xyxy[i].tolist()]
            area = max(1, (x2 - x1) * (y2 - y1))
            if (area / frame_area) < self._cfg.vehicle_min_area_ratio:
                continue
            vehicles.append({"bbox": (x1, y1, x2, y2), "conf": conf})
        return self._deduplicate(vehicles)

    @staticmethod
    def _deduplicate(vehicles: list[dict[str, Any]], iou_threshold: float = 0.75) -> list[dict[str, Any]]:
        """Remove overlapping cross-class boxes that survive model NMS."""
        ordered = sorted(vehicles, key=lambda item: float(item.get("conf", 0.0)), reverse=True)
        kept: list[dict[str, Any]] = []
        for candidate in ordered:
            bbox = tuple(candidate["bbox"])
            if any(_bbox_iou(bbox, tuple(existing["bbox"])) >= iou_threshold for existing in kept):
                continue
            kept.append(candidate)
        return kept


def _bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    intersection_width = max(0, min(ax2, bx2) - max(ax1, bx1))
    intersection_height = max(0, min(ay2, by2) - max(ay1, by1))
    intersection = intersection_width * intersection_height
    if intersection <= 0:
        return 0.0
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return intersection / max(1, area_a + area_b - intersection)
