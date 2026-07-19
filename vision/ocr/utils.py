#!/usr/bin/env python3
import os
import string
import sys
from functools import lru_cache

import cv2


PADDLE_LANGS = tuple(
    dict.fromkeys(
        lang.strip().lower()
        for lang in os.getenv("PADDLE_OCR_LANGS", "pt,en").split(",")
        if lang.strip()
    )
) or ("en",)
PADDLE_USE_GPU = os.getenv("PADDLE_USE_GPU", "0").strip().lower() in {"1", "true", "yes"}
PADDLE_SHOW_LOG = os.getenv("PADDLE_SHOW_LOG", "0").strip().lower() in {"1", "true", "yes"}
OCR_EARLY_STOP_SCORE = float(os.getenv("OCR_EARLY_STOP_SCORE", "98"))
PLATE_PATTERNS = ("LLLDDDD", "LLLDLDD")

DICT_CHAR_TO_INT = {"O": "0", "I": "1", "J": "3", "A": "4", "G": "6", "S": "5"}
DICT_INT_TO_CHAR = {"0": "O", "1": "I", "3": "J", "4": "A", "6": "G", "5": "S"}


def _is_letter(ch):
    return ch in string.ascii_uppercase or ch in DICT_INT_TO_CHAR


def _is_digit(ch):
    return ch in string.digits or ch in DICT_CHAR_TO_INT


def _matches_pattern(text, pattern):
    if len(text) != len(pattern):
        return False
    for idx, token in enumerate(pattern):
        if token == "L" and not _is_letter(text[idx]):
            return False
        if token == "D" and not _is_digit(text[idx]):
            return False
    return True


def _format_pattern(text, pattern):
    chars = []
    for idx, token in enumerate(pattern):
        if token == "L":
            chars.append(DICT_INT_TO_CHAR.get(text[idx], text[idx]))
        else:
            chars.append(DICT_CHAR_TO_INT.get(text[idx], text[idx]))
    return "".join(chars)


def _limpar_texto(texto):
    return "".join(ch for ch in (texto or "").upper() if ch.isalnum())


def _preparar_imagem_ocr(imagem):
    if imagem is None:
        return None
    if len(imagem.shape) == 2:
        return cv2.cvtColor(imagem, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB)


def _iter_ocr_pairs(node):
    if node is None:
        return
    if isinstance(node, (list, tuple)):
        if len(node) == 2 and isinstance(node[0], str):
            yield node[0], node[1]
            return
        for item in node:
            yield from _iter_ocr_pairs(item)


def _normalizar_conf(conf):
    try:
        conf_float = float(conf)
    except (TypeError, ValueError):
        return 0.0
    return conf_float * 100.0 if conf_float <= 1.2 else conf_float


@lru_cache(maxsize=4)
def carregar_paddle(lang):
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise ImportError(
            (
                "Dependencias ausentes no interpretador ativo.\n"
                f"Python: {sys.version.split()[0]} | Executavel: {sys.executable}\n"
                "Use Python 3.11 e instale: pip install paddlepaddle==2.6.2 paddleocr==2.9.1"
            )
        ) from exc

    kwargs = {
        "lang": lang,
        "use_gpu": PADDLE_USE_GPU,
        "show_log": PADDLE_SHOW_LOG,
        "use_angle_cls": False,
    }

    try:
        return PaddleOCR(**kwargs)
    except Exception:
        if lang != "en":
            kwargs["lang"] = "en"
            return PaddleOCR(**kwargs)
        raise


def _rodar_paddle(ocr, imagem, det=False):
    try:
        if det:
            return ocr.ocr(imagem, det=True, rec=True, cls=False)
        return ocr.ocr(imagem, det=False, rec=True, cls=False)
    except TypeError:
        return ocr.ocr(imagem)
    except Exception:
        return []


def run_ocr(imagem, lang):
    imagem_ocr = _preparar_imagem_ocr(imagem)
    if imagem_ocr is None:
        return "", 0.0

    ocr = carregar_paddle(lang)
    pairs = list(_iter_ocr_pairs(_rodar_paddle(ocr, imagem_ocr, det=False)))
    if not pairs:
        pairs = list(_iter_ocr_pairs(_rodar_paddle(ocr, imagem_ocr, det=True)))
    if not pairs:
        return "", 0.0

    texto_limpo = _limpar_texto("".join(text for text, _ in pairs))
    confs = [_normalizar_conf(conf) for _, conf in pairs]
    score = sum(confs) / len(confs) if confs else 0.0
    return texto_limpo, score


def deskew(imagem):
    if imagem is None:
        return imagem

    edges = cv2.Canny(imagem, 50, 150)
    coords = cv2.findNonZero(edges)
    if coords is None or len(coords) < 10:
        return imagem

    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 1.0:
        return imagem

    h, w = imagem.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        imagem,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def aparar_bordas_verticais(imagem):
    if imagem is None:
        return imagem

    h = imagem.shape[0]
    if h <= 120:
        return imagem

    corte_topo = max(6, min(int(round(h * 0.12)), 22))
    corte_base = max(3, min(int(round(h * 0.04)), 12))
    if corte_topo + corte_base >= h - 30:
        return imagem
    return imagem[corte_topo : h - corte_base]


def extrair_candidato(texto, score, origem, lang):
    if len(texto) != 7:
        return None
    for pattern in PLATE_PATTERNS:
        if _matches_pattern(texto, pattern):
            return {
                "placa": _format_pattern(texto, pattern),
                "score": float(score),
                "pattern": pattern,
                "origem": origem,
                "lang": lang,
            }
    return None


def consolidar_candidatos(candidatos):
    melhores_por_placa = {}
    for cand in candidatos:
        atual = melhores_por_placa.get(cand["placa"])
        if atual is None or cand["score"] > atual["score"]:
            melhores_por_placa[cand["placa"]] = cand
    return sorted(
        melhores_por_placa.values(),
        key=lambda item: item["score"],
        reverse=True,
    )


def montar_resultado(placa_final, score, candidatos, placa_recortada, placa_recortada_processada):
    return {
        "placa_final": placa_final,
        "score": float(score),
        "candidatos": candidatos,
        "placa_recortada": placa_recortada,
        "placa_recortada_processada": placa_recortada_processada,
    }


def unpack_possivel_placa(item):
    if isinstance(item, dict):
        return (
            item.get("placa_recortada"),
            item.get("placa_recortada_processada"),
            item,
        )
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return item[0], item[1], None
    return None, None, None


def attach_candidate_metadata(resultado, candidate_index: int, meta) -> dict:
    resultado["candidate_index"] = int(candidate_index)
    if isinstance(meta, dict):
        if "bbox" in meta:
            resultado["bbox"] = [int(v) for v in meta["bbox"]]
        if "det_conf" in meta:
            resultado["det_conf"] = float(meta["det_conf"])
    return resultado
