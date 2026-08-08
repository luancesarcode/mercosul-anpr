"""Visual plate-style hints used only to resolve OCR ambiguities."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

MERCOSUL_PATTERN = "LLLDLDD"
BLUE_MIN = np.array([90, 60, 40], dtype=np.uint8)
BLUE_MAX = np.array([140, 255, 255], dtype=np.uint8)


def mascara_azul_mercosul(plate_crop: Any) -> Any | None:
    """Return the HSV mask used to locate the Mercosur blue band."""
    if plate_crop is None or getattr(plate_crop, "size", 0) == 0:
        return None
    if len(plate_crop.shape) != 3 or plate_crop.shape[2] != 3:
        return None
    hsv = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, BLUE_MIN, BLUE_MAX)


def inferir_padrao_visual(plate_crop: Any) -> str | None:
    """Infer Mercosur style from a strong blue band at the top of the crop."""
    blue_mask = mascara_azul_mercosul(plate_crop)
    if blue_mask is None:
        return None

    height, width = blue_mask.shape
    split = max(1, int(round(height * 0.32)))
    top_ratio = float((blue_mask[:split] > 0).mean())
    lower_ratio = float((blue_mask[split:] > 0).mean()) if split < height else 0.0
    if top_ratio >= 0.08 and top_ratio >= max(0.03, lower_ratio * 2.0):
        return MERCOSUL_PATTERN

    closed = cv2.morphologyEx(
        blue_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, width // 80), 3)),
    )
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(closed, connectivity=8)
    for index in range(1, count):
        _x, y, band_width, band_height, area = [int(value) for value in stats[index]]
        if band_width <= 0 or band_height <= 0:
            continue
        fill_ratio = area / (band_width * band_height)
        if band_width / width < 0.25 or band_width / band_height < 3.0 or fill_ratio < 0.25:
            continue
        if (y + (band_height / 2.0)) / height <= 0.70:
            return MERCOSUL_PATTERN

    contours, _hierarchy = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:3]:
        if cv2.contourArea(contour) < (height * width * 0.01):
            continue
        (center_x, center_y), (rect_width, rect_height), _angle = cv2.minAreaRect(contour)
        _ = center_x
        long_side = max(rect_width, rect_height)
        short_side = max(1.0, min(rect_width, rect_height))
        if long_side / width >= 0.25 and long_side / short_side >= 3.0 and center_y / height <= 0.70:
            return MERCOSUL_PATTERN
    return None
