"""Tests for in-memory browser-camera processing sessions."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import cv2
import numpy as np
import pytest

from mercosul_anpr.api.realtime import (
    InvalidRealtimeFrame,
    RealtimeSessionBusy,
    RealtimeSessionManager,
    RealtimeSessionNotFound,
)


class _FakeService:
    def __init__(self) -> None:
        self.received_shapes: list[tuple[int, ...]] = []

    def create_realtime_processor(self) -> object:
        return object()

    def process_realtime_frame(self, _processor: object, frame: Any, frame_idx: int) -> Any:
        self.received_shapes.append(frame.shape)
        return SimpleNamespace(
            frame_idx=frame_idx,
            annotated_frame=frame,
            vehicles=[{"bbox": (0, 0, 100, 100)}],
            plates=[
                {
                    "vehicle_track_id": 7,
                    "text": "BRA9J14",
                    "text_conf": 94.25,
                    "text_pattern": "LLLDLDD",
                    "det_conf": 0.91,
                    "bbox": [10, 20, 100, 50],
                }
            ],
            metrics=SimpleNamespace(
                elapsed_ms=125.5,
                fps=7.97,
                stage_ms={"vehicle": 40.0, "plate_ocr": 80.0, "render": 5.5},
            ),
        )


def _jpeg(width: int = 640, height: int = 480) -> bytes:
    image = np.full((height, width, 3), 180, dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_realtime_session_processes_sequential_frames_without_disk() -> None:
    service = _FakeService()
    manager = RealtimeSessionManager(service, max_dimension=320, jpeg_quality=75)  # type: ignore[arg-type]
    session = manager.create_session()

    first = manager.process_frame(session["id"], _jpeg())
    second = manager.process_frame(session["id"], _jpeg())

    assert first["frame"] == 1
    assert second["frame"] == 2
    assert first["vehicles"] == 1
    assert first["plates"][0]["text"] == "BRA9J14"
    assert first["inference_fps"] == 7.97
    assert service.received_shapes == [(240, 320, 3), (240, 320, 3)]
    prefix, payload = first["annotated_image"].split(",", maxsplit=1)
    assert prefix == "data:image/jpeg;base64"
    assert base64.b64decode(payload).startswith(b"\xff\xd8")
    assert manager.close_session(session["id"]) is True
    assert manager.active_count() == 0


def test_realtime_manager_allows_only_one_session() -> None:
    manager = RealtimeSessionManager(_FakeService())  # type: ignore[arg-type]
    manager.create_session()
    with pytest.raises(RealtimeSessionBusy):
        manager.create_session()


def test_realtime_manager_rejects_invalid_or_unknown_frames() -> None:
    manager = RealtimeSessionManager(_FakeService())  # type: ignore[arg-type]
    session = manager.create_session()
    with pytest.raises(InvalidRealtimeFrame):
        manager.process_frame(session["id"], b"not-an-image")
    manager.close_session(session["id"])
    with pytest.raises(RealtimeSessionNotFound):
        manager.process_frame(session["id"], _jpeg())


def test_realtime_manager_does_not_expire_a_frame_in_progress() -> None:
    manager = RealtimeSessionManager(_FakeService(), session_ttl_seconds=30)  # type: ignore[arg-type]
    created = manager.create_session()
    session = manager._sessions[created["id"]]
    session.last_activity -= 60
    session.frame_lock.acquire()

    try:
        assert manager.active_count() == 1
    finally:
        session.frame_lock.release()

    assert manager.active_count() == 0
