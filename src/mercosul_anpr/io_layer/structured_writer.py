"""JSON and CSV persistence for the public result contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from mercosul_anpr.domain.results import ProcessingResult


class StructuredResultWriter:
    """Persist the same result in machine-readable formats."""

    def __init__(self, media_path: Path) -> None:
        self.json_path = media_path.with_suffix(".json")
        self.csv_path = media_path.with_suffix(".csv")

    def write(self, result: ProcessingResult) -> tuple[Path, Path]:
        """Write JSON and consolidated CSV atomically enough for local use."""
        result.artifacts["json"] = self.json_path.name
        result.artifacts["csv"] = self.csv_path.name
        self.json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "schema_version",
                    "run_id",
                    "track_id",
                    "plate",
                    "confidence",
                    "first_frame",
                    "last_frame",
                    "occurrences",
                ],
            )
            writer.writeheader()
            for vehicle in result.vehicles:
                writer.writerow(
                    {
                        "schema_version": result.schema_version,
                        "run_id": result.run_id,
                        "track_id": vehicle.track_id if vehicle.track_id is not None else "",
                        "plate": vehicle.plate,
                        "confidence": f"{vehicle.confidence:.2f}",
                        "first_frame": vehicle.first_frame,
                        "last_frame": vehicle.last_frame,
                        "occurrences": vehicle.occurrences,
                    }
                )
        return self.json_path, self.csv_path
