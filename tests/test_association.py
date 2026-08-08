"""Tests for plate-to-vehicle association."""

from __future__ import annotations

from mercosul_anpr.core.config import AssociationConfig
from mercosul_anpr.pipeline.associator import associar_placa_ao_veiculo


def _cfg() -> AssociationConfig:
    return AssociationConfig(
        use_roi_detection=True,
        use_hybrid_association=True,
        association_threshold=0.10,
        association_weights=(0.5, 0.3, 0.2),
        roi_cache_ttl=2,
    )


def test_association_prefers_vehicle_containing_plate() -> None:
    vehicles = [
        {"bbox": (10, 10, 120, 120)},
        {"bbox": (130, 10, 240, 120)},
    ]
    plate = (20, 70, 70, 100)
    idx = associar_placa_ao_veiculo(plate, vehicles, _cfg())
    assert idx == 0


def test_association_returns_none_when_no_match() -> None:
    vehicles = [{"bbox": (10, 10, 60, 60)}]
    plate = (200, 200, 240, 230)
    idx = associar_placa_ao_veiculo(plate, vehicles, _cfg())
    assert idx is None
