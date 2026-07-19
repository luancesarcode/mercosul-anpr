#!/usr/bin/env python3
import cv2

from .utils import (
    OCR_EARLY_STOP_SCORE,
    PADDLE_LANGS,
    aparar_bordas_verticais,
    attach_candidate_metadata,
    consolidar_candidatos,
    deskew,
    extrair_candidato,
    montar_resultado,
    run_ocr,
    unpack_possivel_placa,
)


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _texto_qualidade_bonus(texto: str, has_valid_pattern: bool) -> float:
    texto_raw = (texto or "").upper()
    texto_limpo = "".join(ch for ch in texto_raw if ch.isalnum())
    bonus = 0.0
    if has_valid_pattern:
        bonus += 25.0
    if len(texto_limpo) == 7:
        bonus += 10.0
    elif len(texto_limpo) in {6, 8}:
        bonus += 4.0
    if texto_limpo and texto_limpo == texto_raw:
        bonus += 3.0
    return bonus


def _score_global_result(resultado: dict) -> float:
    texto = str(resultado.get("placa_final") or "")
    score = max(0.0, min(100.0, _as_float(resultado.get("score"), 0.0)))
    candidatos = resultado.get("candidatos") or []
    has_valid_pattern = any(
        isinstance(candidato, dict) and candidato.get("pattern")
        for candidato in candidatos
    )
    det_conf = max(0.0, _as_float(resultado.get("det_conf"), 0.0))
    return score + _texto_qualidade_bonus(texto, has_valid_pattern) + (det_conf * 5.0)


def _build_candidate_result(candidate_index: int, item):
    placa_recortada, placa_recortada_processada, meta = unpack_possivel_placa(item)
    if placa_recortada is None or placa_recortada_processada is None:
        return None

    placa_proc = aparar_bordas_verticais(placa_recortada_processada)
    if placa_proc is None or placa_proc.size == 0:
        return None

    placa_cinza = cv2.cvtColor(placa_recortada, cv2.COLOR_BGR2GRAY)
    imagens_para_ocr = [
        ("gray", placa_cinza),
        ("thresh", placa_proc),
        ("deskew", deskew(placa_proc)),
    ]

    resultados = []
    candidatos_validos = []
    early_stop = False

    for origem, imagem_ocr in imagens_para_ocr:
        if imagem_ocr is None or imagem_ocr.size == 0:
            continue
        for lang in PADDLE_LANGS:
            texto, score = run_ocr(imagem_ocr, lang)
            if not texto:
                continue

            resultado = {
                "texto": texto,
                "score": float(score),
                "origem": origem,
                "lang": lang,
            }
            resultados.append(resultado)

            candidato = extrair_candidato(texto, score, origem, lang)
            if candidato:
                candidatos_validos.append(candidato)
                if candidato["score"] >= OCR_EARLY_STOP_SCORE:
                    early_stop = True
                    break
        if early_stop:
            break

    if candidatos_validos:
        candidatos = consolidar_candidatos(candidatos_validos)
        melhor = candidatos[0]
        base = montar_resultado(
            melhor["placa"],
            melhor["score"],
            candidatos,
            placa_recortada,
            placa_proc,
        )
        return attach_candidate_metadata(base, candidate_index, meta)

    if resultados:
        melhor = max(resultados, key=lambda item: (item["score"], len(item["texto"])))
        fallback = {
            "placa": melhor["texto"],
            "score": melhor["score"],
            "pattern": None,
            "origem": melhor["origem"],
            "lang": melhor["lang"],
        }
        base = montar_resultado(
            fallback["placa"],
            fallback["score"],
            [fallback],
            placa_recortada,
            placa_proc,
        )
        return attach_candidate_metadata(base, candidate_index, meta)

    return None


def aplicar_ocr(possiveis_placas):
    best_result = None
    best_rank = float("-inf")

    for candidate_index, item in enumerate(possiveis_placas):
        candidate_result = _build_candidate_result(candidate_index, item)
        if not candidate_result:
            continue

        rank = _score_global_result(candidate_result)
        if rank > best_rank:
            best_rank = rank
            best_result = candidate_result

    return best_result
