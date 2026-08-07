"""Classical fallback for images that already contain an isolated plate."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def inferir_bbox_placa_isolada(image: Any) -> tuple[int, int, int, int] | None:
    """Infer a plate bbox from a dominant Mercosur blue band.

    This intentionally conservative fallback targets product-style or cropped
    plate images that object detectors often miss because the plate fills most
    of the canvas. Regular vehicle scenes continue to use YOLO detections.
    """
    if image is None or not hasattr(image, "shape") or len(image.shape) != 3:
        return None

    height, width = image.shape[:2]
    if height < 60 or width < 160:
        return None

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(
        hsv,
        np.array([90, 60, 40], dtype=np.uint8),
        np.array([140, 255, 255], dtype=np.uint8),
    )
    close_width = max(3, width // 100)
    blue_mask = cv2.morphologyEx(
        blue_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (close_width, 3)),
    )

    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(blue_mask, connectivity=8)
    bands: list[tuple[float, int, int, int, int]] = []
    for index in range(1, count):
        x, y, band_width, band_height, area = [int(value) for value in stats[index]]
        if band_width <= 0 or band_height <= 0:
            continue
        width_ratio = band_width / width
        height_ratio = band_height / height
        aspect_ratio = band_width / band_height
        fill_ratio = area / (band_width * band_height)
        if width_ratio < 0.45 or not 0.03 <= height_ratio <= 0.30:
            continue
        if aspect_ratio < 4.0 or fill_ratio < 0.35:
            continue
        bands.append((width_ratio * fill_ratio, x, y, band_width, band_height))

    if not bands:
        return None

    _score, band_x, band_y, band_width, band_height = max(bands, key=lambda item: item[0])
    pad_x = max(2, round(band_width * 0.015))
    x1 = max(0, band_x - pad_x)
    x2 = min(width, band_x + band_width + pad_x)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    foreground = ((gray < 235) | (hsv[:, :, 1] > 45)).astype(np.uint8)
    row_active = (np.mean(foreground[:, x1:x2], axis=1) > 0.02).astype(np.uint8).reshape(-1, 1)
    gap_size = max(5, round(band_height * 0.30))
    row_active = cv2.morphologyEx(
        row_active,
        cv2.MORPH_CLOSE,
        np.ones((gap_size, 1), dtype=np.uint8),
    ).reshape(-1)

    center = min(height - 1, band_y + (band_height // 2))
    if not row_active[center]:
        return None
    y1 = center
    while y1 > 0 and row_active[y1 - 1]:
        y1 -= 1
    y2 = center + 1
    while y2 < height and row_active[y2]:
        y2 += 1

    pad_y = max(2, round((y2 - y1) * 0.02))
    y1 = max(0, y1 - pad_y)
    y2 = min(height, y2 + pad_y)
    candidate_width = x2 - x1
    candidate_height = y2 - y1
    candidate_aspect = candidate_width / max(1, candidate_height)
    if candidate_height < 40 or not 2.4 <= candidate_aspect <= 6.5:
        return None
    return x1, y1, x2, y2
