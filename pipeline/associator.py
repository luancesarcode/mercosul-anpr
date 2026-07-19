"""Plate-to-vehicle association strategies."""

from __future__ import annotations

import math
from typing import Any

from core.config import AssociationConfig
from pipeline.tracker import iou_caixas


def _contida_na_caixa(placa: tuple[int, int, int, int], veiculo: tuple[int, int, int, int]) -> bool:
    px1, py1, px2, py2 = placa
    vx1, vy1, vx2, vy2 = veiculo
    return px1 >= vx1 and py1 >= vy1 and px2 <= vx2 and py2 <= vy2


def _center_distance_score(plate_bbox: tuple[int, int, int, int], vehicle_bbox: tuple[int, int, int, int]) -> float:
    pcx = (plate_bbox[0] + plate_bbox[2]) / 2.0
    pcy = (plate_bbox[1] + plate_bbox[3]) / 2.0
    vcx = (vehicle_bbox[0] + vehicle_bbox[2]) / 2.0
    vcy = (vehicle_bbox[1] + vehicle_bbox[3]) / 2.0

    dist = math.hypot(pcx - vcx, pcy - vcy)
    diag = math.hypot(vehicle_bbox[2] - vehicle_bbox[0], vehicle_bbox[3] - vehicle_bbox[1])
    if diag <= 1e-6:
        return 0.0
    normalized = min(1.0, dist / diag)
    return max(0.0, 1.0 - normalized)


def _size_ratio_score(plate_bbox: tuple[int, int, int, int], vehicle_bbox: tuple[int, int, int, int]) -> float:
    plate_area = max(1.0, (plate_bbox[2] - plate_bbox[0]) * (plate_bbox[3] - plate_bbox[1]))
    vehicle_area = max(1.0, (vehicle_bbox[2] - vehicle_bbox[0]) * (vehicle_bbox[3] - vehicle_bbox[1]))
    ratio = plate_area / vehicle_area
    target = 0.045
    error = abs(ratio - target) / max(target, 1e-6)
    return max(0.0, 1.0 - min(1.0, error))


def _hybrid_score(
    plate_bbox: tuple[int, int, int, int],
    vehicle_bbox: tuple[int, int, int, int],
    weights: tuple[float, float, float],
) -> float:
    iou_score = iou_caixas(plate_bbox, vehicle_bbox)
    center_score = _center_distance_score(plate_bbox, vehicle_bbox)
    size_score = _size_ratio_score(plate_bbox, vehicle_bbox)
    score = (weights[0] * iou_score) + (weights[1] * center_score) + (weights[2] * size_score)
    if _contida_na_caixa(plate_bbox, vehicle_bbox):
        score += 0.10
    return max(0.0, min(1.0, score))


def associar_placa_ao_veiculo(
    plate_bbox: tuple[int, int, int, int],
    vehicles: list[dict[str, Any]],
    config: AssociationConfig,
) -> int | None:
    """Associate plate to vehicle using hybrid score with legacy fallback."""
    if not vehicles:
        return None

    best_idx: int | None = None
    best_score = float("-inf")
    if config.use_hybrid_association:
        for idx, vehicle in enumerate(vehicles):
            score = _hybrid_score(plate_bbox, tuple(vehicle["bbox"]), config.association_weights)
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is not None and best_score >= config.association_threshold:
            return best_idx

    choices: list[tuple[int, int]] = []
    for idx, vehicle in enumerate(vehicles):
        vehicle_bbox = tuple(vehicle["bbox"])
        if _contida_na_caixa(plate_bbox, vehicle_bbox):
            area = max(1, (vehicle_bbox[2] - vehicle_bbox[0]) * (vehicle_bbox[3] - vehicle_bbox[1]))
            choices.append((area, idx))

    if not choices:
        return None
    choices.sort(key=lambda item: item[0])
    return choices[0][1]
