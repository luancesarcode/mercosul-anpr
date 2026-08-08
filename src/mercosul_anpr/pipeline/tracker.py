"""Simple IoU tracker for vehicle detections."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mercosul_anpr.core.config import TrackingConfig


def iou_caixas(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Compute intersection-over-union between two bounding boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union


@dataclass
class IoUTracker:
    """Track vehicles across frames using IoU matching."""

    config: TrackingConfig
    state: dict[int, dict[str, Any]] = field(default_factory=dict)
    next_track_id: int = 1

    def update(self, vehicles: list[dict[str, Any]], frame_idx: int) -> list[dict[str, Any]]:
        """Match detections with existing tracks and update tracker state."""
        unmatched = set(range(len(vehicles)))
        matched_track_ids: set[int] = set()

        for track_id in self._ordered_tracks():
            best_idx = self._find_best_match(track_id, vehicles, unmatched)
            if best_idx is None:
                continue
            self._update_matched_track(track_id, vehicles[best_idx], frame_idx)
            self._annotate_detection(vehicles[best_idx], track_id)
            unmatched.remove(best_idx)
            matched_track_ids.add(track_id)

        self._create_tracks_for_unmatched(vehicles, unmatched, frame_idx, matched_track_ids)
        self._age_unmatched_tracks(matched_track_ids)
        return vehicles

    def _ordered_tracks(self) -> list[int]:
        return sorted(self.state.keys(), key=lambda tid: int(self.state[tid].get("hits", 0)), reverse=True)

    def _find_best_match(
        self,
        track_id: int,
        vehicles: list[dict[str, Any]],
        unmatched: set[int],
    ) -> int | None:
        track = self.state.get(track_id)
        if not isinstance(track, dict):
            return None

        track_bbox = tuple(track.get("bbox", (0, 0, 0, 0)))
        best_idx: int | None = None
        best_iou = self.config.track_iou
        for idx in list(unmatched):
            iou = iou_caixas(track_bbox, tuple(vehicles[idx]["bbox"]))
            if iou > best_iou:
                best_iou = iou
                best_idx = idx
        return best_idx

    def _update_matched_track(self, track_id: int, detection: dict[str, Any], frame_idx: int) -> None:
        hits = int(self.state[track_id].get("hits", 0)) + 1
        self.state[track_id] = {
            "bbox": detection["bbox"],
            "hits": hits,
            "missed": 0,
            "last_frame": frame_idx,
        }

    def _annotate_detection(self, detection: dict[str, Any], track_id: int) -> None:
        hits = int(self.state[track_id].get("hits", 1))
        detection["track_id"] = track_id
        detection["track_hits"] = hits
        detection["confirmed"] = hits >= self.config.track_min_hits

    def _create_tracks_for_unmatched(
        self,
        vehicles: list[dict[str, Any]],
        unmatched: set[int],
        frame_idx: int,
        matched_track_ids: set[int],
    ) -> None:
        for idx in sorted(unmatched):
            track_id = self.next_track_id
            self.next_track_id += 1
            detection = vehicles[idx]
            self.state[track_id] = {
                "bbox": detection["bbox"],
                "hits": 1,
                "missed": 0,
                "last_frame": frame_idx,
            }
            detection["track_id"] = track_id
            detection["track_hits"] = 1
            detection["confirmed"] = self.config.track_min_hits <= 1
            matched_track_ids.add(track_id)

    def _age_unmatched_tracks(self, matched_track_ids: set[int]) -> None:
        stale: list[int] = []
        for track_id, track in self.state.items():
            if track_id in matched_track_ids:
                continue
            missed = int(track.get("missed", 0)) + 1
            track["missed"] = missed
            if missed > self.config.track_max_age:
                stale.append(track_id)
        for track_id in stale:
            self.state.pop(track_id, None)

    def active_ids(self) -> set[int]:
        """Return active track IDs."""
        return set(self.state.keys())
