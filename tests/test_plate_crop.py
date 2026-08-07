"""Tests for the conservative isolated-plate fallback."""

from __future__ import annotations

import numpy as np

from mercosul_anpr.vision.plate_crop import inferir_bbox_placa_isolada


def test_infer_isolated_plate_from_dominant_blue_band() -> None:
    image = np.full((450, 680, 3), 250, dtype=np.uint8)
    image[110:335, 8:672] = 230
    image[115:180, 14:666] = (190, 80, 20)
    image[110:115, 8:672] = 10
    image[330:335, 8:672] = 10
    image[180:330, 8:14] = 10
    image[180:330, 666:672] = 10

    bbox = inferir_bbox_placa_isolada(image)

    assert bbox is not None
    x1, y1, x2, y2 = bbox
    assert x1 <= 14 and x2 >= 666
    assert y1 <= 115 and y2 >= 330


def test_rejects_generic_blue_scene() -> None:
    image = np.full((450, 680, 3), (190, 80, 20), dtype=np.uint8)
    assert inferir_bbox_placa_isolada(image) is None
