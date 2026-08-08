"""Plate detection module with global and ROI detection strategies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
from ultralytics import YOLO

from mercosul_anpr.core.config import DetectionConfig
from mercosul_anpr.vision.plate_crop import inferir_bbox_placa_isolada


@dataclass
class _RoiCacheEntry:
    frame_idx: int
    relative_candidates: list[dict[str, Any]]


class PlateDetector:
    """YOLO-based plate detector supporting ROI and temporal cache."""

    def __init__(self, model_path: Path, detection_config: DetectionConfig, roi_cache_ttl: int = 0) -> None:
        self._model = YOLO(str(model_path))
        self._cfg = detection_config
        self._roi_cache_ttl = max(0, int(roi_cache_ttl))
        self._roi_cache: dict[int, _RoiCacheEntry] = {}

    def detect_global(self, frame: Any, device: str | int) -> list[dict[str, Any]]:
        """Run detection over full frame and return plate candidates."""
        boxes, confs = self._predict_boxes(frame, device)
        return self._build_candidates(frame, boxes, confs, offset=(0, 0), vehicle_track_id=None)

    def detect_cropped_plate(self, frame: Any) -> list[dict[str, Any]]:
        """Return a conservative candidate when the image itself is a plate crop."""
        bbox = inferir_bbox_placa_isolada(frame)
        if bbox is None:
            return []
        x1, y1, x2, y2 = bbox
        crop = frame[y1:y2, x1:x2]
        candidate = self._make_candidate(bbox, crop, 0.60, offset=(0, 0), vehicle_track_id=None)
        return [candidate] if candidate else []

    def reset(self) -> None:
        """Clear per-source temporal state while preserving the loaded model."""
        self._roi_cache.clear()

    def detect_by_vehicle_rois(
        self,
        frame: Any,
        vehicles: list[dict[str, Any]],
        frame_idx: int,
        device: str | int,
    ) -> list[dict[str, Any]]:
        """Detect plates in each vehicle ROI with cache reuse."""
        candidates: list[dict[str, Any]] = []
        for vehicle in vehicles:
            track_id = vehicle.get("track_id")
            bbox = tuple(vehicle.get("bbox", (0, 0, 0, 0)))
            if not bbox or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue

            roi = frame[bbox[1] : bbox[3], bbox[0] : bbox[2]]
            if roi is None or roi.size == 0:
                continue

            track_int = int(track_id) if isinstance(track_id, int) else None
            roi_candidates = self._resolve_roi_candidates(roi, bbox, track_int, frame_idx, device)
            candidates.extend(roi_candidates)

        self._evict_stale_cache(frame_idx)
        return candidates

    def _resolve_roi_candidates(
        self,
        roi: Any,
        bbox: tuple[int, int, int, int],
        track_id: int | None,
        frame_idx: int,
        device: str | int,
    ) -> list[dict[str, Any]]:
        if track_id is not None:
            cached = self._roi_cache.get(track_id)
            if cached and (frame_idx - cached.frame_idx) <= self._roi_cache_ttl:
                return self._restore_from_relative_cache(roi, bbox, track_id, cached.relative_candidates)

        boxes, confs = self._predict_boxes(roi, device)
        fresh = self._build_candidates(roi, boxes, confs, offset=(bbox[0], bbox[1]), vehicle_track_id=track_id)
        if track_id is not None and self._roi_cache_ttl > 0:
            self._roi_cache[track_id] = _RoiCacheEntry(
                frame_idx=frame_idx,
                relative_candidates=self._to_relative_cache(fresh, bbox),
            )
        return fresh

    def _predict_boxes(self, image: Any, device: str | int) -> tuple[list[list[float]], list[float]]:
        result = self._model.predict(
            source=image,
            conf=self._cfg.plate_conf,
            iou=self._cfg.plate_iou,
            max_det=max(1, int(self._cfg.max_plates)),
            imgsz=self._cfg.img_size,
            device=device,
            augment=False,
            verbose=False,
        )[0]

        if result.boxes is None or len(result.boxes) == 0:
            result = self._model.predict(
                source=image,
                conf=self._cfg.plate_recall_conf,
                iou=self._cfg.plate_iou,
                max_det=max(1, int(self._cfg.max_plates)),
                imgsz=self._cfg.img_size,
                device=device,
                augment=True,
                verbose=False,
            )[0]

        if result.boxes is None or len(result.boxes) == 0:
            return [], []

        boxes = result.boxes.xyxy.cpu().numpy().tolist()
        confs = result.boxes.conf.cpu().numpy().tolist()
        return boxes, confs

    def _build_candidates(
        self,
        image: Any,
        boxes: list[list[float]],
        confs: list[float],
        offset: tuple[int, int],
        vehicle_track_id: int | None,
    ) -> list[dict[str, Any]]:
        height, width = image.shape[:2]
        order = sorted(range(len(confs)), key=lambda idx: confs[idx], reverse=True)[: max(1, int(self._cfg.max_plates))]
        candidates: list[dict[str, Any]] = []

        for idx in order:
            x1, y1, x2, y2 = [int(v) for v in boxes[idx][:4]]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            crop_bbox = self._expand_bbox(x1, y1, x2, y2, width, height)
            crop = image[crop_bbox[1] : crop_bbox[3], crop_bbox[0] : crop_bbox[2]]
            if crop is None or crop.size == 0:
                continue
            candidates.append(self._make_candidate(crop_bbox, crop, float(confs[idx]), offset, vehicle_track_id))
        return candidates

    def _expand_bbox(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        max_w: int,
        max_h: int,
    ) -> tuple[int, int, int, int]:
        width = x2 - x1
        height = y2 - y1
        if width < 16 or height < 8:
            return x1, y1, x1, y1
        pad_x = int(width * 0.04)
        pad_y = int(height * 0.10)
        return (
            max(0, x1 - pad_x),
            max(0, y1 - pad_y),
            min(max_w, x2 + pad_x),
            min(max_h, y2 + pad_y),
        )

    def _make_candidate(
        self,
        crop_bbox: tuple[int, int, int, int],
        crop: Any,
        det_conf: float,
        offset: tuple[int, int],
        vehicle_track_id: int | None,
    ) -> dict[str, Any]:
        if crop_bbox[2] <= crop_bbox[0] or crop_bbox[3] <= crop_bbox[1]:
            return {}
        processed = self._processar_recorte_placa(crop)
        bbox_global = [
            crop_bbox[0] + offset[0],
            crop_bbox[1] + offset[1],
            crop_bbox[2] + offset[0],
            crop_bbox[3] + offset[1],
        ]
        candidate = {
            "bbox": bbox_global,
            "det_conf": det_conf,
            "placa_recortada": crop,
            "placa_recortada_processada": processed,
        }
        if vehicle_track_id is not None:
            candidate["vehicle_track_id"] = vehicle_track_id
        return candidate

    def _processar_recorte_placa(self, image_crop: Any) -> Any:
        gray = cv2.cvtColor(image_crop, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def _to_relative_cache(
        self,
        candidates: list[dict[str, Any]],
        vehicle_bbox: tuple[int, int, int, int],
    ) -> list[dict[str, Any]]:
        vx1, vy1, vx2, vy2 = vehicle_bbox
        vw = max(1, vx2 - vx1)
        vh = max(1, vy2 - vy1)
        relative: list[dict[str, Any]] = []
        for cand in candidates:
            x1, y1, x2, y2 = [int(v) for v in cand.get("bbox", [0, 0, 0, 0])]
            relative.append(
                {
                    "bbox_rel": [
                        max(0.0, min(1.0, (x1 - vx1) / vw)),
                        max(0.0, min(1.0, (y1 - vy1) / vh)),
                        max(0.0, min(1.0, (x2 - vx1) / vw)),
                        max(0.0, min(1.0, (y2 - vy1) / vh)),
                    ],
                    "det_conf": float(cand.get("det_conf", 0.0)),
                }
            )
        return relative

    def _restore_from_relative_cache(
        self,
        roi: Any,
        vehicle_bbox: tuple[int, int, int, int],
        track_id: int,
        relative_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        height, width = roi.shape[:2]
        vx1, vy1, _vx2, _vy2 = vehicle_bbox
        restored: list[dict[str, Any]] = []
        for cached in relative_candidates:
            rx1, ry1, rx2, ry2 = cached.get("bbox_rel", [0, 0, 0, 0])
            x1, y1 = int(rx1 * width), int(ry1 * height)
            x2, y2 = int(rx2 * width), int(ry2 * height)
            if x2 <= x1 or y2 <= y1:
                continue
            crop_bbox = self._expand_bbox(x1, y1, x2, y2, width, height)
            crop = roi[crop_bbox[1] : crop_bbox[3], crop_bbox[0] : crop_bbox[2]]
            if crop is None or crop.size == 0:
                continue
            candidate = self._make_candidate(
                crop_bbox,
                crop,
                float(cached.get("det_conf", 0.0)),
                offset=(vx1, vy1),
                vehicle_track_id=track_id,
            )
            if candidate:
                restored.append(candidate)
        return restored

    def _evict_stale_cache(self, frame_idx: int) -> None:
        if self._roi_cache_ttl <= 0:
            self._roi_cache.clear()
            return
        stale = [
            track_id
            for track_id, entry in self._roi_cache.items()
            if (frame_idx - entry.frame_idx) > self._roi_cache_ttl
        ]
        for track_id in stale:
            self._roi_cache.pop(track_id, None)
