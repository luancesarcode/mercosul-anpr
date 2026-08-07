"""Reproducible accuracy and latency benchmark CLI."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from mercosul_anpr.application.service import ProcessingService
from mercosul_anpr.core.config import load_app_config
from mercosul_anpr.core.constants import PROJECT_ROOT
from mercosul_anpr.vision.ocr_rules import normalizar_texto_placa


def positional_character_accuracy(expected: str, predicted: str) -> tuple[int, int]:
    """Return matching and expected character counts without hiding length errors."""
    expected = normalizar_texto_placa(expected)
    predicted = normalizar_texto_placa(predicted)
    matches = sum(left == right for left, right in zip(expected, predicted, strict=False))
    return matches, len(expected)


def run_benchmark(manifest_path: Path, output_root: Path) -> dict:
    """Process an authorized manifest and write a machine-readable report."""
    config = load_app_config(PROJECT_ROOT)
    service = ProcessingService(config)
    cases: list[dict] = []
    report_dir = output_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_dir.mkdir(parents=True, exist_ok=True)

    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows, start=1):
        permission = (row.get("permission") or "").strip()
        if not permission:
            raise ValueError(f"Linha {index}: informe a base legal/permissão do exemplo")
        source = (manifest_path.parent / (row.get("path") or "")).resolve()
        expected = normalizar_texto_placa(row.get("expected_plate"))
        result = service.process(source, output_dir=report_dir / f"case-{index:04d}")
        best = max(result.vehicles, key=lambda item: item.confidence, default=None)
        predicted = best.plate if best else ""
        char_matches, char_total = positional_character_accuracy(expected, predicted)
        cases.append(
            {
                "path": str(source),
                "expected": expected,
                "predicted": predicted,
                "exact_match": predicted == expected,
                "character_matches": char_matches,
                "character_total": char_total,
                "latency_ms": result.duration_ms,
                "hardware": row.get("hardware") or "not-informed",
                "source_provenance": row.get("source") or "not-informed",
                "permission": permission,
            }
        )

    total = len(cases)
    char_total = sum(case["character_total"] for case in cases)
    report = {
        "benchmark_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path.resolve()),
        "samples": total,
        "exact_plate_accuracy": (sum(case["exact_match"] for case in cases) / total) if total else 0.0,
        "character_accuracy": (
            sum(case["character_matches"] for case in cases) / char_total if char_total else 0.0
        ),
        "mean_latency_ms": (sum(case["latency_ms"] for case in cases) / total) if total else 0.0,
        "cases": cases,
    }
    (report_dir / "benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    """Run the benchmark from a CSV manifest."""
    parser = argparse.ArgumentParser(description="Benchmark reproduzível do Mercosul ANPR.")
    parser.add_argument("manifest", type=Path, help="CSV com caminhos, gabarito e permissão de uso.")
    parser.add_argument("--output", type=Path, default=Path("runs/benchmarks"))
    args = parser.parse_args(argv)
    report = run_benchmark(args.manifest, args.output)
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
