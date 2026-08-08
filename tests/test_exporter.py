"""Tests for browser-compatible media export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

import mercosul_anpr.render.exporter as exporter_module
from mercosul_anpr.render.exporter import OutputExporter


class _FakeWriter:
    def __init__(self, opened: bool) -> None:
        self.opened = opened
        self.released = False
        self.frames: list[Any] = []

    def isOpened(self) -> bool:  # noqa: N802 - mirrors OpenCV
        return self.opened

    def write(self, frame: Any) -> None:
        self.frames.append(frame)

    def release(self) -> None:
        self.released = True


def test_video_export_prefers_h264_mp4(monkeypatch: Any, tmp_path: Path) -> None:
    writer = _FakeWriter(opened=True)
    calls: list[tuple[str, int]] = []

    def fake_writer(path: str, fourcc: int, _fps: float, _size: tuple[int, int]) -> _FakeWriter:
        calls.append((path, fourcc))
        return writer

    monkeypatch.setattr(exporter_module.sys, "platform", "linux")
    monkeypatch.setattr(exporter_module.cv2, "VideoWriter", fake_writer)
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    exporter = OutputExporter(tmp_path, Path("entrada.mp4"), source_is_image=False, fps=25.0)

    exporter.write_frame(frame)
    exporter.close()

    assert exporter.output_path == tmp_path / "entrada.mp4"
    assert calls[0][1] == exporter_module.cv2.VideoWriter_fourcc(*"avc1")
    assert len(writer.frames) == 1
    assert writer.frames[0] is frame
    assert writer.released is True


def test_video_export_falls_back_to_webm(monkeypatch: Any, tmp_path: Path) -> None:
    failed = _FakeWriter(opened=False)
    webm = _FakeWriter(opened=True)
    writers = iter((failed, webm))
    paths: list[str] = []

    def fake_writer(path: str, _fourcc: int, _fps: float, _size: tuple[int, int]) -> _FakeWriter:
        paths.append(path)
        return next(writers)

    monkeypatch.setattr(exporter_module.sys, "platform", "linux")
    monkeypatch.setattr(exporter_module.cv2, "VideoWriter", fake_writer)
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    exporter = OutputExporter(tmp_path, Path("entrada.mp4"), source_is_image=False, fps=25.0)

    exporter.write_frame(frame)

    assert failed.released is True
    assert paths == [str(tmp_path / "entrada.mp4"), str(tmp_path / "entrada.webm")]
    assert exporter.output_path == tmp_path / "entrada.webm"
    assert len(webm.frames) == 1
    assert webm.frames[0] is frame
