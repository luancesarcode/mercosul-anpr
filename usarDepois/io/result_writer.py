"""Result and runtime log writer with incremental flushing."""

from __future__ import annotations

import logging
from pathlib import Path


class ResultWriter:
    """Write textual run output incrementally to disk and console."""

    def __init__(self, output_path: Path, runtime_logger: logging.Logger) -> None:
        self.output_path = output_path
        self.runtime_logger = runtime_logger
        self.text_path = output_path.with_suffix(".txt")
        self._fh = self.text_path.open("w", encoding="utf-8")

    def write_line(self, text: str) -> None:
        """Write line to console and text log file immediately."""
        print(text)
        self._fh.write(text + "\n")
        self._fh.flush()

    def log_frame_event(
        self,
        frame_idx: int,
        vehicle_count: int,
        plate_text: str,
        conf: float,
        track_id: int | None,
    ) -> None:
        """Write structured frame log in production format."""
        vehicle_token = track_id if track_id is not None else -1
        self.runtime_logger.info(
            "FRAME=%d VEHICLE=%d PLATE=%s CONF=%.4f DETECTED=%d",
            frame_idx,
            vehicle_token,
            plate_text,
            conf,
            vehicle_count,
        )

    def log_profile_event(self, frame_idx: int, fps: float, elapsed_ms: float) -> None:
        """Write structured profiling metrics per frame."""
        self.runtime_logger.info("METRIC FRAME=%d FPS=%.2f ELAPSED_MS=%.2f", frame_idx, fps, elapsed_ms)

    def close(self) -> None:
        """Release text file handle."""
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self) -> "ResultWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
