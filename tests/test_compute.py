"""Tests for compute-device discovery and safe selection."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from mercosul_anpr.application.compute import (
    inspect_compute_capabilities,
    normalize_compute_preference,
    resolve_compute_device,
)


class FakeCuda:
    def __init__(self, available: bool) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def device_count(self) -> int:
        return 1 if self._available else 0

    def get_device_name(self, index: int) -> str:
        assert index == 0
        return "NVIDIA Test GPU"


def test_normalizes_compute_preference_aliases() -> None:
    assert normalize_compute_preference("CUDA") == "nvidia"
    assert normalize_compute_preference("gpu") == "nvidia"
    assert normalize_compute_preference("invalid") == "auto"
    with pytest.raises(ValueError):
        normalize_compute_preference("invalid", strict=True)


def test_inspection_reports_cuda_device(monkeypatch) -> None:
    fake_torch = SimpleNamespace(
        __version__="2.5.1+cu124",
        version=SimpleNamespace(cuda="12.4"),
        cuda=FakeCuda(True),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("mercosul_anpr.application.compute.shutil.which", lambda _name: "nvidia-smi")

    status = inspect_compute_capabilities()

    assert status["available"] is True
    assert status["devices"] == ["NVIDIA Test GPU"]
    assert resolve_compute_device("auto", status) == 0
    assert resolve_compute_device("nvidia", status) == 0


def test_cpu_is_safe_fallback_without_cuda(monkeypatch) -> None:
    fake_torch = SimpleNamespace(
        __version__="2.5.1+cpu",
        version=SimpleNamespace(cuda=None),
        cuda=FakeCuda(False),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr("mercosul_anpr.application.compute.shutil.which", lambda _name: None)

    status = inspect_compute_capabilities()

    assert status["available"] is False
    assert resolve_compute_device("auto", status) == "cpu"
    assert resolve_compute_device("cpu", status) == "cpu"
    with pytest.raises(ValueError, match="somente CPU"):
        resolve_compute_device("nvidia", status)
