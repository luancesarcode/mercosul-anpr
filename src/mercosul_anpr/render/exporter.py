"""Output exporter for annotated image/video artifacts."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class OutputExporter:
    """Persist processed frames to image or MP4 output."""

    def __init__(self, output_dir: Path, source_path: Path | str | int, source_is_image: bool, fps: float) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.source_is_image = source_is_image
        self.fps = float(fps) if math.isfinite(float(fps)) and float(fps) > 0.0 else 30.0
        self.output_path = self._resolve_output_path(source_path)
        self._writer: cv2.VideoWriter | None = None
        self._image_written = False
        self._video_size: tuple[int, int] | None = None

    def _resolve_output_path(self, source_path: Path | str | int) -> Path:
        if isinstance(source_path, Path):
            stem = source_path.stem
        elif isinstance(source_path, int):
            stem = f"live_{source_path}"
        else:
            raw = str(source_path).strip()
            if raw.isdigit():
                stem = f"live_{raw}"
            elif "://" in raw:
                stem = "live_stream"
            else:
                stem = Path(raw).stem or "output"
        suffix = ".jpg" if self.source_is_image else ".mp4"
        return self.output_dir / f"{stem}{suffix}"

    def write_frame(self, frame: Any) -> None:
        """Write one processed frame to target output."""
        if self.source_is_image:
            self._write_image(frame)
            return
        self._write_video_frame(frame)

    def _write_image(self, frame: Any) -> None:
        if self._image_written:
            return
        try:
            ok = cv2.imwrite(str(self.output_path), frame)
        except cv2.error:
            ok = False
        if not ok:
            encoded_ok, encoded = cv2.imencode(".jpg", np.asarray(frame))
            if encoded_ok:
                try:
                    encoded.tofile(self.output_path)
                    ok = True
                except OSError:
                    ok = False
        if not ok:
            raise RuntimeError(f"[erro] Falha ao salvar imagem: {self.output_path}")
        self._image_written = True

    def _write_video_frame(self, frame: Any) -> None:
        if self._writer is None:
            height, width = frame.shape[:2]
            self._video_size = (width, height)
            self._writer = self._open_browser_video_writer(self._video_size)
        self._writer.write(frame)

    def _open_browser_video_writer(self, size: tuple[int, int]) -> cv2.VideoWriter:
        """Prefer browser-native H.264, then WebM, keeping MP4V only as a last resort."""
        candidates = (
            (".mp4", "avc1"),
            (".webm", "VP80"),
            (".mp4", "mp4v"),
        )
        attempted_paths: set[Path] = set()
        for suffix, codec in candidates:
            candidate_path = self.output_path.with_suffix(suffix)
            attempted_paths.add(candidate_path)
            writer = self._create_video_writer(candidate_path, codec, size)
            if writer.isOpened():
                self.output_path = candidate_path
                return writer
            writer.release()
            candidate_path.unlink(missing_ok=True)

        attempted = ", ".join(str(path) for path in sorted(attempted_paths))
        raise RuntimeError(f"[erro] Falha ao iniciar gravacao de video compativel: {attempted}")

    def _create_video_writer(self, path: Path, codec: str, size: tuple[int, int]) -> cv2.VideoWriter:
        fourcc = cv2.VideoWriter_fourcc(*codec)
        if sys.platform == "win32" and codec == "avc1":
            return cv2.VideoWriter(str(path), cv2.CAP_MSMF, fourcc, self.fps, size)
        return cv2.VideoWriter(str(path), fourcc, self.fps, size)

    def close(self) -> None:
        """Finalize and release writer resources."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def __enter__(self) -> OutputExporter:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
