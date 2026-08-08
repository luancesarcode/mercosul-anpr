"""Overlay rendering for boxes, labels, and debugger panel."""

from __future__ import annotations

from typing import Any

import cv2


def obter_estilo_texto(frame_shape: tuple[int, int], fator: float = 1.0) -> tuple[float, int, int]:
    """Compute dynamic text and box style from frame resolution."""
    height, width = frame_shape
    factor = max(width / 1280.0, height / 720.0)
    scale = max(0.70, min(2.40, 0.70 * factor * fator))
    text_thickness = max(2, int(round(2.0 * scale)))
    box_thickness = max(2, int(round(1.8 * scale)))
    return scale, text_thickness, box_thickness


def desenhar_rotulo(
    frame: Any,
    text: str,
    x: int,
    y: int,
    box_color: tuple[int, int, int],
    scale: float,
    thickness: int,
) -> None:
    """Draw readable text over colored rectangle."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x = max(0, x)
    y = max(th + baseline, y)
    cv2.rectangle(frame, (x, y - th - baseline), (x + tw, y + baseline), box_color, -1)
    cv2.putText(frame, text, (x, y), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def desenhar_debugger_superior_esquerda(frame: Any, linhas: list[str]) -> Any:
    """Draw debugger lines on top-left corner."""
    out = frame
    scale, thickness, _ = obter_estilo_texto(out.shape[:2], fator=0.88)
    y = max(24, int(round(26 * scale)))

    for linha in linhas:
        (_, height), baseline = cv2.getTextSize(linha, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        y = max(y, height + baseline + 2)
        desenhar_rotulo(out, linha, 10, y, (30, 30, 30), scale, thickness)
        y += height + baseline + max(6, int(round(8 * scale)))
    return out


def desenhar_anotacoes(frame: Any, vehicles: list[dict[str, Any]], plates: list[dict[str, Any]]) -> Any:
    """Draw all detections and OCR labels in output frame."""
    out = frame.copy()
    v_scale, v_text_thick, v_box_thick = obter_estilo_texto(out.shape[:2], fator=0.90)
    p_scale, p_text_thick, p_box_thick = obter_estilo_texto(out.shape[:2], fator=0.84)
    v_top_offset = max(6, int(round(10 * v_scale)))
    p_top_offset = max(6, int(round(10 * p_scale)))
    p_bottom_offset = max(22, int(round(28 * p_scale)))

    for vehicle in vehicles:
        x1, y1, x2, y2 = vehicle["bbox"]
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), v_box_thick)
        label = f"{float(vehicle.get('conf', 0.0)):.2f}"
        desenhar_rotulo(out, label, x1, y1 - v_top_offset, (0, 255, 0), v_scale, v_text_thick)

    for plate in plates:
        x1, y1, x2, y2 = plate["bbox"]
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 0, 0), p_box_thick)
        det_label = f"plate {float(plate.get('det_conf', 0.0)):.2f}"
        plate_text = plate.get("text") or "N/A"
        desenhar_rotulo(out, det_label, x1, y1 - p_top_offset, (255, 0, 0), p_scale, p_text_thick)
        desenhar_rotulo(out, plate_text, x1, y2 + p_bottom_offset, (255, 0, 0), p_scale, p_text_thick)
    return out
