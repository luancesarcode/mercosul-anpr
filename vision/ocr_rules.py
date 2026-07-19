"""OCR post-processing rules for Brazilian plate patterns."""

from __future__ import annotations

import re
import string
from types import MappingProxyType
from typing import Any

from core.constants import PLATE_PATTERNS

REGEX_PLACA_ANTIGA = re.compile(r"^[A-Z]{3}\d{4}$")
REGEX_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}\d[A-Z]\d{2}$")
MAPA_LETRA_PARA_DIGITO = MappingProxyType({"O": "0", "I": "1", "S": "5", "B": "8", "D": "0"})
MAPA_DIGITO_PARA_LETRA = MappingProxyType({"0": "O", "1": "I", "5": "S", "8": "B"})


def normalizar_texto_placa(text: str | None) -> str:
    """Normalize OCR text to uppercase alphanumeric format.

    Args:
        text: Raw OCR text.

    Returns:
        Sanitized plate text.
    """
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())


def validar_padrao_placa(text: str) -> str | None:
    """Validate whether text matches old or Mercosur plate pattern."""
    clean = normalizar_texto_placa(text)
    if REGEX_PLACA_ANTIGA.fullmatch(clean):
        return PLATE_PATTERNS[0]
    if REGEX_PLACA_MERCOSUL.fullmatch(clean):
        return PLATE_PATTERNS[1]
    return None


def _corrigir_char_para_tipo(char: str, tipo: str) -> tuple[str | None, bool]:
    if tipo == "L":
        if char in string.ascii_uppercase:
            return char, False
        if char in MAPA_DIGITO_PARA_LETRA:
            return MAPA_DIGITO_PARA_LETRA[char], True
        return None, False
    if tipo == "D":
        if char in string.digits:
            return char, False
        if char in MAPA_LETRA_PARA_DIGITO:
            return MAPA_LETRA_PARA_DIGITO[char], True
        return None, False
    return None, False


def _tentar_corrigir_para_padrao(text: str, padrao: str) -> tuple[str, int] | None:
    if len(text) != len(padrao):
        return None

    corrigida: list[str] = []
    mudancas = 0
    for char, tipo in zip(text, padrao):
        convertido, mudou = _corrigir_char_para_tipo(char, tipo)
        if convertido is None:
            return None
        corrigida.append(convertido)
        if mudou:
            mudancas += 1

    texto_corrigido = "".join(corrigida)
    if validar_padrao_placa(texto_corrigido) != padrao:
        return None
    return texto_corrigido, mudancas


def validar_e_corrigir_placa(text: str | None) -> tuple[str, str, int] | None:
    """Validate plate text and apply ambiguity corrections when needed.

    Args:
        text: Candidate OCR text.

    Returns:
        Tuple with corrected text, pattern and change-count when valid.
    """
    clean = normalizar_texto_placa(text)
    if not clean:
        return None

    padrao = validar_padrao_placa(clean)
    if padrao:
        return clean, padrao, 0

    if len(clean) != 7:
        return None

    candidatos: list[tuple[str, str, int]] = []
    for padrao_tentativa in PLATE_PATTERNS:
        resultado = _tentar_corrigir_para_padrao(clean, padrao_tentativa)
        if resultado is None:
            continue
        texto_corrigido, mudancas = resultado
        candidatos.append((texto_corrigido, padrao_tentativa, mudancas))

    if not candidatos:
        return None

    candidatos.sort(key=lambda item: (item[2], 0 if item[1] == PLATE_PATTERNS[1] else 1))
    return candidatos[0]


def escolher_texto_ocr(ocr_result: dict[str, Any] | None) -> tuple[str, float, str | None]:
    """Pick the best valid OCR text from OCR candidates.

    Args:
        ocr_result: OCR engine output payload.

    Returns:
        Best text, confidence score and pattern.
    """
    if not isinstance(ocr_result, dict):
        return "", 0.0, None

    candidates = ocr_result.get("candidatos") or []
    best_text = ""
    best_score = 0.0
    best_pattern: str | None = None
    best_rank = float("-inf")

    for item in candidates:
        if not isinstance(item, dict):
            continue
        resolvido = validar_e_corrigir_placa(item.get("placa"))
        if resolvido is None:
            continue
        text, pattern, mudancas = resolvido
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        rank = score - (mudancas * 2.5)
        if rank > best_rank:
            best_rank = rank
            best_text = text
            best_score = score
            best_pattern = str(pattern)

    if best_text:
        return best_text, best_score, best_pattern

    fallback_raw = ocr_result.get("placa_final")
    resolvido_fallback = validar_e_corrigir_placa(fallback_raw)
    if resolvido_fallback is None:
        return "", 0.0, None

    fallback_text, fallback_pattern, _ = resolvido_fallback
    try:
        fallback_score = float(ocr_result.get("score", 0.0))
    except (TypeError, ValueError):
        fallback_score = 0.0
    return fallback_text, fallback_score, fallback_pattern
