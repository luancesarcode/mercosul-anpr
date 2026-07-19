"""Tests for OCR normalization and selection rules."""

from __future__ import annotations

from vision.ocr_rules import escolher_texto_ocr, validar_e_corrigir_placa


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
    assert score == 89.0
    assert pattern in {"LLLDDDD", "LLLDLDD"}
