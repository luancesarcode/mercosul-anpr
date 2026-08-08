"""Tests for the versioned machine-readable result contract."""

from __future__ import annotations

import csv
import json

from mercosul_anpr.benchmark import positional_character_accuracy
from mercosul_anpr.domain.results import FrameResult, PlateObservation, ProcessingResult, consolidate_vehicles
from mercosul_anpr.io_layer.structured_writer import StructuredResultWriter


def test_consolidates_observations_and_writes_json_csv(tmp_path) -> None:
    observations = [
        PlateObservation(1, 7, "ABC1D23", 90.0, "LLLDLDD", 0.88, [1, 2, 3, 4]),
        PlateObservation(2, 7, "ABC1D23", 94.0, "LLLDLDD", 0.91, [2, 2, 4, 4]),
    ]
    frames = [
        FrameResult(1, 1, 10.0, 100.0, [observations[0]]),
        FrameResult(2, 1, 12.0, 83.3, [observations[1]]),
    ]
    vehicles = consolidate_vehicles(frames)
    result = ProcessingResult(
        run_id="run-1",
        source="input.jpg",
        source_type="image",
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        duration_ms=1000.0,
        frames_processed=2,
        frames=frames,
        vehicles=vehicles,
        artifacts={"media": "input.jpg", "text": "input.txt"},
    )

    json_path, csv_path = StructuredResultWriter(tmp_path / "input.jpg").write(result)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    assert payload["vehicles"][0]["confidence"] == 92.0
    assert payload["vehicles"][0]["occurrences"] == 2
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["plate"] == "ABC1D23"
    assert rows[0]["first_frame"] == "1"


def test_character_accuracy_penalizes_wrong_and_missing_characters() -> None:
    matches, total = positional_character_accuracy("ABC1D23", "ABC1D2")
    assert matches == 6
    assert total == 7
