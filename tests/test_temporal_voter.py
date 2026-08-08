"""Tests for temporal vote and debugger state behavior."""

from __future__ import annotations

from mercosul_anpr.core.config import TrackingConfig
from mercosul_anpr.pipeline.temporal_voter import TemporalVoter


def _config() -> TrackingConfig:
    return TrackingConfig(
        track_iou=0.3,
        track_min_hits=1,
        track_max_age=3,
        plate_vote_window=5,
        plate_switch_dominance_frames=2,
        debugger_window_frames=4,
        plate_min_occurrences=2,
        plate_min_score=70.0,
        ocr_interval_frames=1,
    )


def test_vote_without_track_id_returns_corrected_text() -> None:
    voter = TemporalVoter(_config())
    text, score, pattern = voter.vote(None, "PDHO164", 90.0, frame_idx=1)
    assert text == "PDH0164"
    assert score == 90.0
    assert pattern == "LLLDDDD"


def test_vote_switches_after_dominance_streak() -> None:
    voter = TemporalVoter(_config())

    t1 = voter.vote(1, "PDH2164", 90.0, frame_idx=1)
    assert t1[0] == "PDH2164"

    voter.vote(1, "POH2164", 95.0, frame_idx=2)

    # Second competing value reaches dominance streak and switches
    t3 = voter.vote(1, "POH2164", 96.0, frame_idx=3)
    assert t3[0] == "POH2164"


def test_cleanup_removes_stale_states() -> None:
    voter = TemporalVoter(_config())
    voter.vote(2, "PDH2164", 88.0, frame_idx=1)
    voter.update_debugger([
        {"vehicle_track_id": 2, "text": "PDH2164", "text_conf": 88.0},
    ], frame_idx=1)

    voter.cleanup(active_track_ids=set(), frame_idx=10)
    assert 2 not in voter.vote_state
    assert 2 not in voter.debugger_state


def test_debugger_lines_returns_most_frequent_plate() -> None:
    voter = TemporalVoter(_config())
    plates = [
        {"vehicle_track_id": 1, "text": "PDH2164", "text_conf": 90.0},
        {"vehicle_track_id": 1, "text": "PDH2164", "text_conf": 92.0},
        {"vehicle_track_id": 1, "text": "POH2164", "text_conf": 80.0},
    ]
    voter.update_debugger(plates, frame_idx=1)
    lines = voter.debugger_lines()
    assert lines == ["ID:01 PDH2164"]


def test_get_stable_prediction_returns_state() -> None:
    voter = TemporalVoter(_config())
    voter.vote(3, "PDH2164", 90.0, frame_idx=1)
    text, score, pattern = voter.get_stable_prediction(3)
    assert text == "PDH2164"
    assert score > 0.0
    assert pattern in {"LLLDDDD", "LLLDLDD"}
