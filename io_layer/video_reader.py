"""Input source reader for image, video, webcam and network streams."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import cv2


@dataclass
class FramePacket:
    """Frame payload emitted by input readers."""

    frame_idx: int
    frame: Any


class InputSourceReader:
    """Read frames from image/video/live sources with a uniform interface."""

    def __init__(self, source_path: Path | str | int, image_extensions: set[str]) -> None:
        self.source_path = source_path
        self.image_extensions = {ext.lower() for ext in image_extensions}
        self._cap: cv2.VideoCapture | None = None
        self._is_live = self._detect_live_source(source_path)
        self._is_image = (not self._is_live) and self._is_image_path(source_path)
        self._fps = 30.0
        self._capture_source: str | int = self._resolve_capture_source(source_path)

    @property
    def is_image(self) -> bool:
        """Return whether source is an image file."""
        return self._is_image

    @property
    def fps(self) -> float:
        """Return source fps (30 for images/live when unavailable)."""
        return self._fps

    def open(self) -> None:
        """Initialize source resources."""
        if self._is_image:
            return
        self._cap = cv2.VideoCapture(self._capture_source)
        if not self._cap.isOpened():
            raise RuntimeError(f"[erro] Nao foi possivel abrir video/stream: {self.source_path}")
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0

    def frames(self) -> Iterator[FramePacket]:
        """Yield frames from source."""
        if self._is_image:
            frame = cv2.imread(str(self.source_path))
            if frame is None:
                raise RuntimeError(f"[erro] Nao foi possivel abrir imagem: {self.source_path}")
            yield FramePacket(frame_idx=1, frame=frame)
            return

        if self._cap is None:
            raise RuntimeError("Video source nao inicializado. Chame open() antes de frames().")

        idx = 0
        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            idx += 1
            yield FramePacket(frame_idx=idx, frame=frame)

    def close(self) -> None:
        """Release source resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "InputSourceReader":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _detect_live_source(self, source: Path | str | int) -> bool:
        if isinstance(source, int):
            return True
        if isinstance(source, str):
            raw = source.strip()
            if raw.isdigit():
                return True
            low = raw.lower()
            return low.startswith(("rtsp://", "rtmp://", "http://", "https://"))
        return False

    def _is_image_path(self, source: Path | str | int) -> bool:
        if isinstance(source, Path):
            return source.suffix.lower() in self.image_extensions
        if isinstance(source, str):
            return Path(source).suffix.lower() in self.image_extensions
        return False

    def _resolve_capture_source(self, source: Path | str | int) -> str | int:
        if isinstance(source, int):
            return source
        if isinstance(source, str):
            raw = source.strip()
            if raw.isdigit():
                return int(raw)
            return raw
        return str(source)
