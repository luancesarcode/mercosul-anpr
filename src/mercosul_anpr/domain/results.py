"""Serializable, versioned processing result models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class PlateObservation:
    """One plate observation from a processed frame."""

    frame: int
    track_id: int | None
    text: str
    confidence: float
    pattern: str | None
    detection_confidence: float
    bbox: list[int]


@dataclass(frozen=True)
class FrameResult:
    """Structured metadata for one frame."""

    frame: int
    vehicles: int
    elapsed_ms: float
    fps: float
    plates: list[PlateObservation] = field(default_factory=list)


@dataclass(frozen=True)
class VehicleSummary:
    """Consolidated observations for a tracked vehicle and plate."""

    track_id: int | None
    plate: str
    confidence: float
    first_frame: int
    last_frame: int
    occurrences: int


@dataclass
class ProcessingResult:
    """Top-level result persisted by CLI and returned by the API."""

    run_id: str
    source: str
    source_type: str
    status: str
    started_at: str
    completed_at: str
    duration_ms: float
    frames_processed: int
    frames: list[FrameResult]
    vehicles: list[VehicleSummary]
    artifacts: dict[str, str] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary."""
        return asdict(self)


def consolidate_vehicles(frames: list[FrameResult]) -> list[VehicleSummary]:
    """Consolidate repeated plate observations into stable rows."""
    groups: dict[tuple[int | None, str], list[PlateObservation]] = {}
    for frame in frames:
        for plate in frame.plates:
            groups.setdefault((plate.track_id, plate.text), []).append(plate)

    summaries: list[VehicleSummary] = []
    for (track_id, plate), observations in groups.items():
        confidence = sum(item.confidence for item in observations) / len(observations)
        summaries.append(
            VehicleSummary(
                track_id=track_id,
                plate=plate,
                confidence=round(confidence, 2),
                first_frame=min(item.frame for item in observations),
                last_frame=max(item.frame for item in observations),
                occurrences=len(observations),
            )
        )
    return sorted(summaries, key=lambda item: (item.first_frame, item.track_id or -1, item.plate))
