#!/usr/bin/env python3
import cv2
import numpy as np

from mercosul_anpr.vision.ocr_style import mascara_azul_mercosul


def estimar_inclinacao_faixa_azul(imagem_placa) -> float | None:
    """Estimate plate rotation from a sufficiently large Mercosur blue band."""
    blue_mask = mascara_azul_mercosul(imagem_placa)
    if blue_mask is None:
        return None
    height, width = blue_mask.shape
    closed = cv2.morphologyEx(
        blue_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(5, width // 40), 3)),
    )
    contours, _hierarchy = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < (height * width * 0.015):
        return None
    _center, (rect_width, rect_height), angle = cv2.minAreaRect(contour)
    long_side = max(rect_width, rect_height)
    short_side = max(1.0, min(rect_width, rect_height))
    if long_side / width < 0.25 or long_side / short_side < 3.0:
        return None
    if rect_width < rect_height:
        angle += 90.0
    if angle > 45.0:
        angle -= 90.0
    if abs(angle) < 2.0 or abs(angle) > 30.0:
        return None
    return float(angle)


def corrigir_inclinacao_faixa_azul(imagem_placa, factor: float = 0.60):
    """Rotate a plate crop using a conservative fraction of its blue-band angle."""
    angle = estimar_inclinacao_faixa_azul(imagem_placa)
    if angle is None:
        return None
    height, width = imagem_placa.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle * factor, 1.0)
    return cv2.warpAffine(
        imagem_placa,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def gerar_variantes_ocr(imagem_placa, imagem_binaria=None):
    """Create a small, ordered set of complementary OCR inputs."""
    if imagem_placa is None or imagem_placa.size == 0:
        return []
    cinza = cv2.cvtColor(imagem_placa, cv2.COLOR_BGR2GRAY) if len(imagem_placa.shape) == 3 else imagem_placa.copy()
    altura = max(1, cinza.shape[0])
    escala = min(3.0, max(1.0, 64.0 / altura))
    if escala > 1.05:
        cinza = cv2.resize(cinza, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cinza)
    if imagem_binaria is None or imagem_binaria.size == 0:
        _, binaria = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        binaria = imagem_binaria
        if escala > 1.05:
            binaria = cv2.resize(binaria, (cinza.shape[1], cinza.shape[0]), interpolation=cv2.INTER_NEAREST)
    if float(np.mean(binaria)) < 127.0:
        binaria = cv2.bitwise_not(binaria)
    return [("gray", cinza), ("clahe", clahe), ("thresh", binaria)]
