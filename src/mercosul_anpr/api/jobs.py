"""Small local background-job manager with disk-backed status snapshots."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mercosul_anpr.application.service import ProcessingService

STATUS_PERSIST_INTERVAL_SECONDS = 0.5
STATUS_RETRY_DELAYS_SECONDS = (0.02, 0.05, 0.10, 0.20, 0.40)


@dataclass
class JobRecord:
    """Mutable local job state exposed by the HTTP API."""

    id: str
    filename: str
    status: str = "queued"
    progress: float | None = 0.0
    frames_processed: int = 0
    total_frames: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None

    def public_dict(self) -> dict[str, Any]:
        """Return the stable job response."""
        payload = asdict(self)
        payload.pop("result", None)
        payload["result_url"] = f"/api/v1/jobs/{self.id}/result" if self.status == "completed" else None
        return payload


class JobManager:
    """Serialize model execution while keeping HTTP requests responsive."""

    def __init__(
        self,
        service: ProcessingService,
        jobs_root: Path,
        *,
        timeout_seconds: int,
        retention_hours: int,
    ) -> None:
        self.service = service
        self.jobs_root = jobs_root.resolve()
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = max(30, timeout_seconds)
        self.retention_hours = max(1, retention_hours)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="anpr-job")
        self._persistence_failures = 0

    def submit(self, job_id: str, source_path: Path, filename: str) -> JobRecord:
        """Queue a processing job and return immediately."""
        self.cleanup_expired()
        record = JobRecord(id=job_id, filename=filename)
        with self._lock:
            self._jobs[job_id] = record
            self._persist(record)
        self._executor.submit(self._run, record, source_path)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        """Return a job from memory or its persisted snapshot."""
        with self._lock:
            record = self._jobs.get(job_id)
        if record is not None:
            return record
        record = self._load_snapshot(job_id)
        if record is not None:
            with self._lock:
                self._jobs[job_id] = record
        return record

    def list_jobs(self, limit: int = 100) -> list[JobRecord]:
        """Return known jobs from memory and disk, newest first."""
        records: dict[str, JobRecord] = {}
        with self._lock:
            records.update(self._jobs)
        for directory in self.jobs_root.iterdir():
            if not directory.is_dir() or directory.name in records:
                continue
            record = self._load_snapshot(directory.name)
            if record is not None:
                records[directory.name] = record
        ordered = sorted(records.values(), key=lambda record: record.created_at, reverse=True)
        return ordered[: max(1, limit)]

    def _load_snapshot(self, job_id: str) -> JobRecord | None:
        """Load a persisted job snapshot, tolerating corrupt files."""
        status_path = self.jobs_root / job_id / "status.json"
        if not status_path.is_file():
            return None
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            return JobRecord(**data)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def shutdown(self) -> None:
        """Stop accepting work and let the active job finish."""
        self._executor.shutdown(wait=False, cancel_futures=True)

    def stats(self) -> dict[str, int]:
        """Return aggregate in-memory job counts for local metrics."""
        counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0}
        with self._lock:
            for record in self._jobs.values():
                if record.status in counts:
                    counts[record.status] += 1
        return counts

    def cleanup_expired(self) -> None:
        """Delete job folders older than the configured local retention."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
        for directory in self.jobs_root.iterdir():
            if not directory.is_dir():
                continue
            modified = datetime.fromtimestamp(directory.stat().st_mtime, tz=timezone.utc)
            if modified >= cutoff:
                continue
            resolved = directory.resolve()
            if resolved.parent == self.jobs_root:
                shutil.rmtree(resolved, ignore_errors=True)
                with self._lock:
                    self._jobs.pop(directory.name, None)

    def _run(self, record: JobRecord, source_path: Path) -> None:
        record.status = "running"
        record.started_at = datetime.now(timezone.utc).isoformat()
        self._persist(record)
        deadline = time.monotonic() + self.timeout_seconds
        last_persisted_at = time.monotonic()

        def update_progress(done: int, total: int | None) -> None:
            nonlocal last_persisted_at
            if time.monotonic() > deadline:
                raise TimeoutError(f"Processamento excedeu {self.timeout_seconds} segundos")
            record.frames_processed = done
            record.total_frames = total
            record.progress = round((done / total) * 100.0, 1) if total else None
            now = time.monotonic()
            reached_end = total is not None and done >= total
            if reached_end or (now - last_persisted_at) >= STATUS_PERSIST_INTERVAL_SECONDS:
                self._persist(record)
                last_persisted_at = now

        try:
            output_dir = self.jobs_root / record.id / "output"
            result = self.service.process(
                source_path,
                output_dir=output_dir,
                run_id=record.id,
                progress=update_progress,
            )
            record.status = "completed"
            record.progress = 100.0
            record.result = result.to_dict()
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
        finally:
            record.completed_at = datetime.now(timezone.utc).isoformat()
            self._persist(record)

    def _persist(self, record: JobRecord) -> bool:
        """Persist an atomic status snapshot without interrupting inference on I/O contention."""
        directory = self.jobs_root / record.id
        directory.mkdir(parents=True, exist_ok=True)
        status_path = directory / "status.json"
        with self._lock:
            payload = json.dumps(asdict(record), ensure_ascii=False, indent=2)

        for delay in STATUS_RETRY_DELAYS_SECONDS:
            temporary: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    prefix=".status-",
                    suffix=".tmp",
                    dir=directory,
                    delete=False,
                ) as handle:
                    handle.write(payload + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    temporary = Path(handle.name)
                os.replace(temporary, status_path)
                return True
            except OSError:
                time.sleep(delay)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

        with self._lock:
            self._persistence_failures += 1
        return False
