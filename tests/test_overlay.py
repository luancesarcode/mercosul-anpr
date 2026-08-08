"""Tests for clean user-facing detection overlays."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from mercosul_anpr.render.overlay import desenhar_anotacoes


def test_overlay_does_not_render_internal_track_id(monkeypatch: Any) -> None:
    rendered_texts: list[str] = []
    original_put_text = cv2.putText

    def capture_text(frame: Any, text: str, *args: Any, **kwargs: Any) -> Any:
        rendered_texts.append(text)
        return original_put_text(frame, text, *args, **kwargs)

    monkeypatch.setattr(cv2, "putText", capture_text)
    frame = np.zeros((240, 360, 3), dtype=np.uint8)
    vehicles = [{"bbox": (20, 20, 320, 210), "track_id": 12, "conf": 0.91}]
    plates = [{"bbox": (120, 140, 240, 185), "det_conf": 0.88, "text": "BRA9J14"}]

    desenhar_anotacoes(frame, vehicles, plates)

    assert all("ID:" not in text for text in rendered_texts)
    assert rendered_texts == ["0.91", "plate 0.88", "BRA9J14"]
