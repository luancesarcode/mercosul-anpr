"""Output exporter for annotated image/video artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2


class OutputExporter:
    """Persist processed frames to image or MP4 output."""

    def __init__(self, output_dir: Path, source_path: Path | str | int, source_is_image: bool, fps: float) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.source_is_image = source_is_image
        self.fps = fps
        self.output_path = self._resolve_output_path(source_path)
        self._writer: cv2.VideoWriter | None = None
        self._image_written = False

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
        ok = cv2.imwrite(str(self.output_path), frame)
        if not ok:
            raise RuntimeError(f"[erro] Falha ao salvar imagem: {self.output_path}")
        self._image_written = True

    def _write_video_frame(self, frame: Any) -> None:
        if self._writer is None:
            height, width = frame.shape[:2]
            self._writer = cv2.VideoWriter(
                str(self.output_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                self.fps,
                (width, height),
            )
        self._writer.write(frame)

    def close(self) -> None:
        """Finalize and release writer resources."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None

    def __enter__(self) -> "OutputExporter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
