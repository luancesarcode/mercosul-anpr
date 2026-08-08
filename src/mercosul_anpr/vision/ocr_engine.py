"""OCR engine wrapper for PaddleOCR-based plate reading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mercosul_anpr.vision.ocr.aplicar_ocr import aplicar_ocr
from mercosul_anpr.vision.ocr.utils import PADDLE_LANGS, carregar_paddle
from mercosul_anpr.vision.ocr_rules import escolher_texto_ocr
from mercosul_anpr.vision.ocr_style import inferir_padrao_visual


@dataclass(frozen=True)
class OCRResult:
    """Normalized OCR output payload."""

    text: str
    score: float
    pattern: str | None
    det_conf: float


class OCREngine:
    """Adapter around existing OCR pipeline with explicit warmup."""

    def warmup(self) -> None:
        """Warm up PaddleOCR model for first language."""
        carregar_paddle(PADDLE_LANGS[0])

    def read_candidate(self, candidate: dict[str, Any]) -> OCRResult:
        """Run OCR on a single plate candidate.

        Args:
            candidate: Plate candidate dictionary containing crop metadata.

        Returns:
            Structured OCR output.
        """
        ocr_result = aplicar_ocr([candidate])
        if not isinstance(ocr_result, dict):
            return OCRResult(text="", score=0.0, pattern=None, det_conf=float(candidate.get("det_conf", 0.0)))

        preferred_pattern = inferir_padrao_visual(candidate.get("placa_recortada"))
        text, score, pattern = escolher_texto_ocr(ocr_result, preferred_pattern)
        det_conf = float(ocr_result.get("det_conf", candidate.get("det_conf", 0.0)))
        return OCRResult(text=text, score=float(score), pattern=pattern, det_conf=det_conf)
