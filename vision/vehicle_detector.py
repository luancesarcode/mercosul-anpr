"""Vehicle detection module powered by YOLO."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ultralytics import YOLO

from core.config import DetectionConfig


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
        return vehicles
