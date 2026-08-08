"""Optional runtime profiling helpers (cProfile and line_profiler)."""

from __future__ import annotations

import cProfile
import pstats
from pathlib import Path
from typing import Any


def start_cprofile(enabled: bool) -> cProfile.Profile | None:
    """Start a cProfile session when enabled.

    Args:
        enabled: Whether profiling should start.

    Returns:
        Active profiler instance, or None when disabled.
    """
    if not enabled:
        return None
    profiler = cProfile.Profile()
    profiler.enable()
    return profiler


def finish_cprofile(profiler: cProfile.Profile | None, output_dir: Path, top: int = 60) -> None:
    """Stop cProfile and write binary and text reports.

    Args:
        profiler: Profiler returned by start_cprofile (or None).
        output_dir: Directory receiving profile_main.prof and profile_main.txt.
        top: Number of rows printed in the text report.
    """
    if profiler is None:
        return
    profiler.disable()
    output_dir.mkdir(parents=True, exist_ok=True)
    profiler.dump_stats(str(output_dir / "profile_main.prof"))
    with (output_dir / "profile_main.txt").open("w", encoding="utf-8") as fh:
        stats = pstats.Stats(profiler, stream=fh)
        stats.sort_stats("cumulative")
        stats.print_stats(top)


def enable_line_profiler(processor: Any, enabled: bool, output_dir: Path) -> Any:
    """Wrap processor.process_frame with line_profiler when available.

    Args:
        processor: Pipeline processor instance to instrument.
        enabled: Whether line profiling should start.
        output_dir: Directory receiving line_profile.txt.

    Returns:
        Active LineProfiler instance, or None when disabled or unavailable.
    """
    if not enabled:
        return None
    try:
        from line_profiler import LineProfiler
    except Exception:
        return None

    profiler = LineProfiler()
    processor.process_frame = profiler(processor.process_frame)  # type: ignore[method-assign]
    profiler.output_path = output_dir / "line_profile.txt"  # type: ignore[attr-defined]
    return profiler


def finalize_line_profiler(profiler: Any) -> None:
    """Write line_profiler stats to the configured output path.

    Args:
        profiler: Profiler returned by enable_line_profiler (or None).
    """
    if profiler is None:
        return
    output_path = getattr(profiler, "output_path", None)
    if output_path is None:
        return
    with Path(output_path).open("w", encoding="utf-8") as fh:
        profiler.print_stats(stream=fh)
