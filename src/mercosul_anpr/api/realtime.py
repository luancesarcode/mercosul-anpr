"""In-memory browser-camera sessions for sequential real-time inference."""

from __future__ import annotations

import base64
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from mercosul_anpr.application.service import ProcessingService


class RealtimeSessionError(RuntimeError):
    """Base error for real-time session operations."""


class RealtimeSessionBusy(RealtimeSessionError):
    """Raised when another local camera session is already active."""


class RealtimeSessionNotFound(RealtimeSessionError):
    """Raised when a session is missing or expired."""


class RealtimeFrameBusy(RealtimeSessionError):
    """Raised when a client sends overlapping frames."""


class InvalidRealtimeFrame(RealtimeSessionError):
    """Raised when uploaded bytes are not a decodable image."""


@dataclass
class RealtimeSession:
    """Mutable state kept only for the lifetime of one browser camera session."""

    id: str
    created_at: float
    last_activity: float
    processor: Any | None = None
    frame_idx: int = 0
    frame_lock: threading.Lock = field(default_factory=threading.Lock)


class RealtimeSessionManager:
    """Own one local camera stream and preserve temporal OCR state between frames."""

    def __init__(
        self,
        service: ProcessingService,
        *,
        session_ttl_seconds: int = 300,
        max_dimension: int = 1280,
        jpeg_quality: int = 82,
    ) -> None:
        self.service = service
        self.session_ttl_seconds = max(30, int(session_ttl_seconds))
        self.max_dimension = max(320, min(2560, int(max_dimension)))
        self.jpeg_quality = max(50, min(95, int(jpeg_quality)))
        self._sessions: dict[str, RealtimeSession] = {}
        self._lock = threading.RLock()

    def create_session(self) -> dict[str, Any]:
        """Reserve and initialize the single supported local camera session."""
        now = time.monotonic()
        with self._lock:
            self._cleanup_stale_locked(now)
            if self._sessions:
                raise RealtimeSessionBusy("Já existe uma sessão de câmera ativa nesta máquina.")
            session = RealtimeSession(id=uuid.uuid4().hex[:12], created_at=now, last_activity=now)
            self._sessions[session.id] = session

        try:
            session.processor = self.service.create_realtime_processor()
        except Exception:
            with self._lock:
                self._sessions.pop(session.id, None)
            raise

        return {
            "id": session.id,
            "status": "ready",
            "expires_in_seconds": self.session_ttl_seconds,
            "frame_url": f"/api/v1/realtime/sessions/{session.id}/frames",
            "close_url": f"/api/v1/realtime/sessions/{session.id}",
        }

    def process_frame(self, session_id: str, encoded_frame: bytes) -> dict[str, Any]:
        """Decode, resize, infer and return one annotated camera frame."""
        session = self._get_session(session_id)
        if not session.frame_lock.acquire(blocking=False):
            raise RealtimeFrameBusy("O frame anterior ainda está sendo processado.")

        try:
            if session.processor is None:
                raise RealtimeFrameBusy("Os modelos ainda estão sendo preparados.")
            frame = self._decode_frame(encoded_frame)
            frame = self._resize_frame(frame)
            session.frame_idx += 1
            processed = self.service.process_realtime_frame(session.processor, frame, session.frame_idx)
            session.last_activity = time.monotonic()
            return self._serialize_frame(session.id, processed)
        finally:
            session.frame_lock.release()

    def close_session(self, session_id: str) -> bool:
        """Forget all temporal state for one browser camera session."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def active_count(self) -> int:
        """Return live sessions after evicting idle clients."""
        with self._lock:
            self._cleanup_stale_locked(time.monotonic())
            return len(self._sessions)

    def shutdown(self) -> None:
        """Release all in-memory session references."""
        with self._lock:
            self._sessions.clear()

    def _get_session(self, session_id: str) -> RealtimeSession:
        now = time.monotonic()
        with self._lock:
            self._cleanup_stale_locked(now)
            session = self._sessions.get(session_id)
            if session is None:
                raise RealtimeSessionNotFound("Sessão de câmera inexistente ou expirada.")
            session.last_activity = now
            return session

    def _cleanup_stale_locked(self, now: float) -> None:
        stale_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.processor is not None
            and not session.frame_lock.locked()
            and (now - session.last_activity) > self.session_ttl_seconds
        ]
        for session_id in stale_ids:
            self._sessions.pop(session_id, None)

    @staticmethod
    def _decode_frame(encoded_frame: bytes) -> Any:
        if not encoded_frame:
            raise InvalidRealtimeFrame("O frame enviado está vazio.")
        buffer = np.frombuffer(encoded_frame, dtype=np.uint8)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if frame is None or frame.size == 0:
            raise InvalidRealtimeFrame("Não foi possível decodificar o frame da câmera.")
        return frame

    def _resize_frame(self, frame: Any) -> Any:
        height, width = frame.shape[:2]
        largest = max(height, width)
        if largest <= self.max_dimension:
            return frame
        scale = self.max_dimension / largest
        target = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        return cv2.resize(frame, target, interpolation=cv2.INTER_AREA)

    def _serialize_frame(self, session_id: str, processed: Any) -> dict[str, Any]:
        success, encoded = cv2.imencode(
            ".jpg",
            processed.annotated_frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
        )
        if not success:
            raise InvalidRealtimeFrame("Não foi possível codificar o frame anotado.")

        plates = [
            {
                "track_id": item.get("vehicle_track_id"),
                "text": str(item.get("text") or "N/A"),
                "confidence": round(float(item.get("text_conf", 0.0)), 2),
                "pattern": item.get("text_pattern"),
                "detection_confidence": round(float(item.get("det_conf", 0.0)), 4),
                "bbox": [int(value) for value in item.get("bbox", [])],
            }
            for item in processed.plates
        ]
        return {
            "session_id": session_id,
            "frame": int(processed.frame_idx),
            "vehicles": len(processed.vehicles),
            "plates": plates,
            "elapsed_ms": round(float(processed.metrics.elapsed_ms), 2),
            "inference_fps": round(float(processed.metrics.fps), 2),
            "stage_ms": {key: round(float(value), 2) for key, value in processed.metrics.stage_ms.items()},
            "annotated_image": f"data:image/jpeg;base64,{base64.b64encode(encoded.tobytes()).decode('ascii')}",
        }
