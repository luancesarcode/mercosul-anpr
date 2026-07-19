"""Tests for IoU tracker behavior."""

from __future__ import annotations

from core.config import TrackingConfig
from pipeline.tracker import IoUTracker, iou_caixas


def test_iou_caixas_overlap() -> None:
    assert 0.14 < iou_caixas((0, 0, 10, 10), (5, 5, 15, 15)) < 0.15


def test_tracker_keeps_id_across_frames() -> None:
    cfg = TrackingConfig(
        track_iou=0.1,
        track_min_hits=2,
        track_max_age=3,
        plate_vote_window=10,
        plate_switch_dominance_frames=3,
        debugger_window_frames=30,
        plate_min_occurrences=2,
        plate_min_score=65.0,
        ocr_interval_frames=1,
    )
    tracker = IoUTracker(cfg)

    frame1 = tracker.update([{"bbox": (10, 10, 100, 100), "conf": 0.9}], frame_idx=1)
    assert frame1[0]["track_id"] == 1
    assert frame1[0]["confirmed"] is False

    frame2 = tracker.update([{"bbox": (12, 12, 102, 102), "conf": 0.8}], frame_idx=2)
    assert frame2[0]["track_id"] == 1
    assert frame2[0]["confirmed"] is True


def test_tracker_removes_stale_tracks() -> None:
    cfg = TrackingConfig(
        track_iou=0.3,
        track_min_hits=1,
        track_max_age=1,
        plate_vote_window=10,
        plate_switch_dominance_frames=3,
        debugger_window_frames=30,
        plate_min_occurrences=2,
        plate_min_score=65.0,
        ocr_interval_frames=1,
    )
    tracker = IoUTracker(cfg)
    tracker.update([{"bbox": (1, 1, 20, 20), "conf": 0.9}], frame_idx=1)
    assert 1 in tracker.state

    tracker.update([], frame_idx=2)
    tracker.update([], frame_idx=3)
    assert 1 not in tracker.state
