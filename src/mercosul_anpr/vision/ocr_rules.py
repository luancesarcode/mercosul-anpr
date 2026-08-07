"""Context-aware OCR post-processing for Brazilian plate patterns."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from mercosul_anpr.core.constants import PLATE_PATTERNS

REGEX_PLACA_ANTIGA = re.compile(r"^[A-Z]{3}\d{4}$")
REGEX_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}\d[A-Z]\d{2}$")

# Confidence points removed for each contextual replacement. The closest
# glyphs have the smallest penalty; weak similarities are deliberately costly.
_LETRA_PARA_DIGITO = MappingProxyType(
    {
        "O": ("0", 1.0),
        "I": ("1", 1.0),
        "S": ("5", 1.25),
        "B": ("8", 1.5),
        "A": ("4", 2.0),
        "G": ("6", 2.0),
        "L": ("1", 2.0),
        "Z": ("2", 2.0),
        "D": ("0", 3.0),
        "J": ("3", 3.0),
        "Q": ("0", 3.0),
        "T": ("7", 3.0),
        "Y": ("7", 4.0),
    }
)
_DIGITO_PARA_LETRA = MappingProxyType(
    {
        "0": ("O", 1.0),
        "1": ("I", 1.0),
        "5": ("S", 1.25),
        "8": ("B", 1.5),
        "2": ("Z", 2.0),
        "4": ("A", 2.0),
        "6": ("G", 2.0),
        "3": ("J", 3.0),
        "7": ("T", 3.0),
    }
)

# Immutable canonical maps kept for callers that only need the replacement.
MAPA_LETRA_PARA_DIGITO = MappingProxyType({char: value[0] for char, value in _LETRA_PARA_DIGITO.items()})
MAPA_DIGITO_PARA_LETRA = MappingProxyType({char: value[0] for char, value in _DIGITO_PARA_LETRA.items()})

MAX_CONTEXTUAL_CHANGES = 2
MAX_CONTEXTUAL_PENALTY = 7.0
MAX_VISUAL_OVERRIDE_CHANGES = 1
MAX_VISUAL_OVERRIDE_PENALTY = 3.0


@dataclass(frozen=True, slots=True)
class PlateResolution:
    """A valid plate interpretation with auditable contextual corrections."""

    text: str
    pattern: str
    changes: int
    penalty: float
    converted_positions: tuple[int, ...]
    reason: str


def normalizar_texto_placa(text: str | None) -> str:
    """Normalize OCR text to uppercase ASCII alphanumeric format."""
    return "".join(ch for ch in (text or "").upper() if ch in string.ascii_uppercase or ch in string.digits)


def validar_padrao_placa(text: str) -> str | None:
    """Validate whether text matches the legacy or Mercosur plate pattern."""
    clean = normalizar_texto_placa(text)
    if REGEX_PLACA_ANTIGA.fullmatch(clean):
        return PLATE_PATTERNS[0]
    if REGEX_PLACA_MERCOSUL.fullmatch(clean):
        return PLATE_PATTERNS[1]
    return None


def _corrigir_char_para_tipo(char: str, tipo: str) -> tuple[str | None, float]:
    if tipo == "L":
        if char in string.ascii_uppercase:
            return char, 0.0
        replacement = _DIGITO_PARA_LETRA.get(char)
        return replacement if replacement is not None else (None, 0.0)
    if tipo == "D":
        if char in string.digits:
            return char, 0.0
        replacement = _LETRA_PARA_DIGITO.get(char)
        return replacement if replacement is not None else (None, 0.0)
    return None, 0.0


def _tentar_corrigir_para_padrao(text: str, padrao: str) -> PlateResolution | None:
    if len(text) != len(padrao):
        return None

    corrected: list[str] = []
    converted_positions: list[int] = []
    penalty = 0.0
    for index, (char, tipo) in enumerate(zip(text, padrao, strict=True), start=1):
        converted, char_penalty = _corrigir_char_para_tipo(char, tipo)
        if converted is None:
            return None
        corrected.append(converted)
        if converted != char:
            converted_positions.append(index)
            penalty += char_penalty

    corrected_text = "".join(corrected)
    changes = len(converted_positions)
    if changes > MAX_CONTEXTUAL_CHANGES or penalty > MAX_CONTEXTUAL_PENALTY:
        return None
    if validar_padrao_placa(corrected_text) != padrao:
        return None
    return PlateResolution(
        text=corrected_text,
        pattern=padrao,
        changes=changes,
        penalty=penalty,
        converted_positions=tuple(converted_positions),
        reason="exact" if changes == 0 else "contextual-pattern",
    )


def gerar_interpretacoes_placa(text: str | None) -> tuple[PlateResolution, ...]:
    """Return all safe pattern interpretations for one seven-character token."""
    clean = normalizar_texto_placa(text)
    if len(clean) != 7:
        return ()

    candidates = [
        candidate
        for pattern in PLATE_PATTERNS
        if (candidate := _tentar_corrigir_para_padrao(clean, pattern)) is not None
    ]
    candidates.sort(
        key=lambda item: (
            item.penalty,
            item.changes,
            PLATE_PATTERNS.index(item.pattern),
            item.text,
        )
    )
    return tuple(candidates)


def resolver_placa_detalhado(
    text: str | None,
    preferred_pattern: str | None = None,
) -> PlateResolution | None:
    """Resolve a plate using format, glyph costs and an optional visual style hint."""
    candidates = gerar_interpretacoes_placa(text)
    if not candidates:
        return None

    exact = next((candidate for candidate in candidates if candidate.changes == 0), None)
    if preferred_pattern in PLATE_PATTERNS:
        preferred = next((candidate for candidate in candidates if candidate.pattern == preferred_pattern), None)
        if preferred is not None:
            baseline = candidates[0]
            extra_changes = preferred.changes - baseline.changes
            extra_penalty = preferred.penalty - baseline.penalty
            may_override_exact = exact is None or exact.pattern == preferred_pattern or (
                extra_changes <= MAX_VISUAL_OVERRIDE_CHANGES
                and extra_penalty <= MAX_VISUAL_OVERRIDE_PENALTY
            )
            if may_override_exact:
                reason = "exact" if preferred.changes == 0 else "visual-pattern"
                return replace(preferred, reason=reason)

    if exact is not None:
        return exact
    return candidates[0]


def validar_e_corrigir_placa(
    text: str | None,
    preferred_pattern: str | None = None,
) -> tuple[str, str, int] | None:
    """Compatibility wrapper returning corrected text, pattern and change count."""
    resolved = resolver_placa_detalhado(text, preferred_pattern)
    if resolved is None:
        return None
    return resolved.text, resolved.pattern, resolved.changes


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def escolher_texto_ocr(
    ocr_result: dict[str, Any] | None,
    preferred_pattern: str | None = None,
) -> tuple[str, float, str | None]:
    """Pick the best valid OCR text and return its penalty-adjusted confidence."""
    if not isinstance(ocr_result, dict):
        return "", 0.0, None

    candidates = ocr_result.get("candidatos") or []
    best_resolution: PlateResolution | None = None
    best_score = 0.0
    best_rank = float("-inf")

    for item in candidates:
        if not isinstance(item, dict):
            continue
        raw_text = item.get("raw_window") or item.get("placa")
        resolved = resolver_placa_detalhado(raw_text, preferred_pattern)
        if resolved is None:
            continue
        raw_score = max(0.0, min(100.0, _as_float(item.get("score"))))
        trimmed_chars = max(0, int(_as_float(item.get("trimmed_chars"))))
        effective_score = max(0.0, raw_score - resolved.penalty - (trimmed_chars * 1.5))
        occurrences = max(1, int(_as_float(item.get("occurrences"), 1.0)))
        rank = effective_score + (min(3, occurrences - 1) * 2.0)
        if rank > best_rank:
            best_rank = rank
            best_resolution = resolved
            best_score = effective_score

    if best_resolution is not None:
        return best_resolution.text, best_score, best_resolution.pattern

    fallback_raw = ocr_result.get("placa_final")
    resolved_fallback = resolver_placa_detalhado(fallback_raw, preferred_pattern)
    if resolved_fallback is None:
        return "", 0.0, None

    fallback_score = max(0.0, min(100.0, _as_float(ocr_result.get("score"))))
    adjusted_score = max(0.0, fallback_score - resolved_fallback.penalty)
    return resolved_fallback.text, adjusted_score, resolved_fallback.pattern
