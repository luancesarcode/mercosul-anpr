"""Tests for configuration precedence and path resolution."""

from __future__ import annotations

from pathlib import Path

from mercosul_anpr.core.config import load_app_config


def test_environment_values_are_used_without_cli_overrides(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANPR_SOURCE", "inputs/from-env.mp4")
    monkeypatch.setenv("ANPR_RUNS_DIR", "outputs/from-env")

    config = load_app_config(tmp_path)

    assert config.source_path == (tmp_path / "inputs/from-env.mp4").resolve()
    assert config.runs_dir == (tmp_path / "outputs/from-env").resolve()


def test_explicit_values_take_precedence_over_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANPR_SOURCE", "inputs/from-env.mp4")

    config = load_app_config(
        tmp_path,
        overrides={"source_path": "inputs/from-cli.mp4"},
    )

    assert config.source_path == (tmp_path / "inputs/from-cli.mp4").resolve()


def test_numeric_configuration_is_clamped_and_weights_are_normalized(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANPR_VEHICLE_CONF", "-1")
    monkeypatch.setenv("ANPR_PLATE_CONF", "2")
    monkeypatch.setenv("ANPR_PLATE_RECALL_CONF", "3")
    monkeypatch.setenv("ANPR_TRACK_IOU", "0")
    monkeypatch.setenv("ANPR_PLATE_TEXT_CONF_MIN", "-20")
    monkeypatch.setenv("ANPR_PLATE_TEXT_CONF_MAX", "250")
    monkeypatch.setenv("ANPR_ASSOC_WEIGHT_IOU", "2")
    monkeypatch.setenv("ANPR_ASSOC_WEIGHT_CENTER", "1")
    monkeypatch.setenv("ANPR_ASSOC_WEIGHT_SIZE", "1")

    config = load_app_config(tmp_path)

    assert config.detection.vehicle_conf == 0.01
    assert config.detection.plate_conf == 1.0
    assert config.detection.plate_recall_conf == 1.0
    assert config.tracking.track_iou == 0.05
    assert config.display.plate_text_conf_min == 0.0
    assert config.display.plate_text_conf_max == 100.0
    assert config.association.association_weights == (0.5, 0.25, 0.25)
