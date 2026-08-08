"""Tests for OCR normalization and selection rules."""

from __future__ import annotations

import cv2
import numpy as np

from mercosul_anpr.vision.ocr.processar_imagem import estimar_inclinacao_faixa_azul, gerar_variantes_ocr
from mercosul_anpr.vision.ocr.utils import consolidar_candidatos, extrair_candidato
from mercosul_anpr.vision.ocr_rules import (
    escolher_texto_ocr,
    gerar_interpretacoes_placa,
    resolver_placa_detalhado,
    validar_e_corrigir_placa,
)
from mercosul_anpr.vision.ocr_style import inferir_padrao_visual


def test_validar_e_corrigir_placa_accepts_valid_text() -> None:
    resolved = validar_e_corrigir_placa("PDH2164")
    assert resolved is not None
    assert resolved[0] == "PDH2164"


def test_validar_e_corrigir_placa_corrects_common_confusion() -> None:
    resolved = validar_e_corrigir_placa("PDHO164")
    assert resolved is not None
    assert resolved[0] == "PDH0164"


def test_escolher_texto_ocr_prefers_valid_candidate() -> None:
    payload = {
        "placa_final": "XXY999",
        "score": 88.0,
        "candidatos": [
            {"placa": "PDHO164", "score": 89.0},
            {"placa": "AB123", "score": 95.0},
        ],
    }
    text, score, pattern = escolher_texto_ocr(payload)
    assert text == "PDH0164"
    assert score == 88.0
    assert pattern in {"LLLDDDD", "LLLDLDD"}


def test_ocr_variants_upscale_small_plate_and_normalize_background() -> None:
    image = np.zeros((20, 80, 3), dtype=np.uint8)
    binary = np.zeros((20, 80), dtype=np.uint8)
    variants = gerar_variantes_ocr(image, binary)
    assert [name for name, _ in variants] == ["gray", "clahe", "thresh"]
    assert variants[0][1].shape[0] >= 60
    assert float(variants[-1][1].mean()) > 127.0


def test_candidate_consensus_receives_rank_bonus() -> None:
    candidates = [
        {"placa": "ABC1D23", "score": 88.0, "pattern": "LLLDLDD"},
        {"placa": "ABC1D23", "score": 87.0, "pattern": "LLLDLDD"},
        {"placa": "XYZ9Z99", "score": 89.0, "pattern": "LLLDLDD"},
    ]
    consolidated = consolidar_candidatos(candidates)
    assert consolidated[0]["placa"] == "ABC1D23"
    assert consolidated[0]["occurrences"] == 2


def test_candidate_selection_prefers_pattern_without_character_conversion() -> None:
    candidate = extrair_candidato("SIK1D75", 87.4, "gray", "en")
    assert candidate is not None
    assert candidate["placa"] == "SIK1D75"
    assert candidate["pattern"] == "LLLDLDD"
    assert candidate["normalization_changes"] == 0


def test_candidate_selection_can_trim_one_spurious_ocr_character() -> None:
    candidate = extrair_candidato("FOZL7H33", 75.0, "deskew", "en")
    assert candidate is not None
    assert candidate["placa"] == "OZL7H33"
    assert candidate["trimmed_chars"] == 1


def test_mercosul_visual_hint_resolves_digit_letter_ambiguity() -> None:
    crop = np.full((100, 300, 3), 230, dtype=np.uint8)
    crop[:30, :] = (190, 80, 20)
    preferred = inferir_padrao_visual(crop)
    resolved = validar_e_corrigir_placa("BCV6189", preferred)
    assert preferred == "LLLDLDD"
    assert resolved is not None
    assert resolved[0] == "BCV6I89"


def test_mercosul_visual_hint_resolves_four_as_letter_a() -> None:
    resolved = validar_e_corrigir_placa("RIO2419", "LLLDLDD")
    assert resolved is not None
    assert resolved[0] == "RIO2A19"


def test_mercosul_visual_hint_resolves_three_as_letter_j() -> None:
    resolved = validar_e_corrigir_placa("BRA9314", "LLLDLDD")
    assert resolved is not None
    assert resolved[0] == "BRA9J14"


def test_contextual_rules_cover_frequent_plate_font_confusions() -> None:
    cases = {
        "P0H2164": "POH2164",
        "ABCL234": "ABC1234",
        "ABCIZ34": "ABC1Z34",
        "A8C1D23": "ABC1D23",
        "ABC1D2S": "ABC1D25",
    }
    for raw, expected in cases.items():
        resolved = resolver_placa_detalhado(raw)
        assert resolved is not None
        assert resolved.text == expected
        assert resolved.converted_positions


def test_exact_valid_plate_is_not_changed_without_visual_evidence() -> None:
    resolved = resolver_placa_detalhado("ABC1234")
    assert resolved is not None
    assert resolved.text == "ABC1234"
    assert resolved.reason == "exact"
    assert resolved.penalty == 0.0


def test_strong_visual_hint_can_override_one_ambiguous_position() -> None:
    resolved = resolver_placa_detalhado("ABC1234", "LLLDLDD")
    assert resolved is not None
    assert resolved.text == "ABC1Z34"
    assert resolved.pattern == "LLLDLDD"
    assert resolved.reason == "visual-pattern"
    assert resolved.converted_positions == (5,)


def test_visual_hint_does_not_exceed_global_conversion_limit() -> None:
    interpretations = gerar_interpretacoes_placa("08C1234")
    assert {item.text for item in interpretations} == {"OBC1234"}
    resolved = resolver_placa_detalhado("08C1234", "LLLDLDD")
    assert resolved is not None
    assert resolved.text == "OBC1234"
    assert resolved.changes == 2


def test_mass_conversion_is_rejected_to_avoid_inventing_a_plate() -> None:
    assert resolver_placa_detalhado("0000000") is None


def test_candidate_keeps_auditable_conversion_metadata() -> None:
    candidate = extrair_candidato("BRA9314", 91.0, "gray", "pt", "LLLDLDD")
    assert candidate is not None
    assert candidate["placa"] == "BRA9J14"
    assert candidate["raw_window"] == "BRA9314"
    assert candidate["converted_positions"] == [5]
    assert candidate["conversion_penalty"] == 3.0
    assert candidate["resolution_reason"] == "visual-pattern"


def test_plain_plate_does_not_force_mercosul_pattern() -> None:
    crop = np.full((100, 300, 3), 230, dtype=np.uint8)
    assert inferir_padrao_visual(crop) is None


def test_blue_band_hint_survives_vertical_padding_and_rotation() -> None:
    crop = np.full((180, 400, 3), 230, dtype=np.uint8)
    crop[55:90, 35:365] = (190, 80, 20)
    center = (crop.shape[1] / 2.0, crop.shape[0] / 2.0)
    matrix = cv2.getRotationMatrix2D(center, -12.0, 1.0)
    rotated = cv2.warpAffine(crop, matrix, (crop.shape[1], crop.shape[0]), borderValue=(230, 230, 230))

    assert inferir_padrao_visual(rotated) == "LLLDLDD"
    angle = estimar_inclinacao_faixa_azul(rotated)
    assert angle is not None
    assert 5.0 <= abs(angle) <= 20.0
