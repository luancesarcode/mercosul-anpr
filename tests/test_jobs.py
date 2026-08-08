"""Tests for resilient local job status persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import mercosul_anpr.api.jobs as jobs_module
from mercosul_anpr.api.jobs import JobManager, JobRecord


def _manager(tmp_path: Path) -> JobManager:
    return JobManager(
        service=cast(Any, object()),
        jobs_root=tmp_path / "jobs",
        timeout_seconds=60,
        retention_hours=1,
    )


def test_status_persistence_retries_atomic_replace(monkeypatch, tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    record = JobRecord(id="retry-job", filename="image.jpg")
    original_replace = os.replace
    attempts = 0

    def flaky_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("temporarily locked")
        return original_replace(source, destination)

    monkeypatch.setattr(jobs_module, "STATUS_RETRY_DELAYS_SECONDS", (0.0, 0.0, 0.0))
    monkeypatch.setattr(jobs_module.os, "replace", flaky_replace)

    assert manager._persist(record) is True
    payload = json.loads((tmp_path / "jobs" / record.id / "status.json").read_text(encoding="utf-8"))
    assert payload["id"] == record.id
    assert attempts == 3
    assert not list((tmp_path / "jobs" / record.id).glob(".status-*.tmp"))
    manager.shutdown()


def test_status_persistence_failure_is_non_fatal(monkeypatch, tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    record = JobRecord(id="locked-job", filename="video.mp4")
    monkeypatch.setattr(jobs_module, "STATUS_RETRY_DELAYS_SECONDS", (0.0,))

    def locked_replace(_source, _destination):
        raise PermissionError("locked")

    monkeypatch.setattr(jobs_module.os, "replace", locked_replace)

    assert manager._persist(record) is False
    assert manager._persistence_failures == 1
    assert not list((tmp_path / "jobs" / record.id).glob(".status-*.tmp"))
    manager.shutdown()


def test_list_jobs_merges_memory_and_disk_newest_first(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    memory_job = JobRecord(id="memory-job", filename="live.jpg", created_at="2024-01-02T00:00:00+00:00")
    manager._jobs[memory_job.id] = memory_job
    manager._persist(memory_job)

    disk_job = JobRecord(id="disk-job", filename="old.mp4", created_at="2024-01-01T00:00:00+00:00")
    disk_dir = tmp_path / "jobs" / disk_job.id
    disk_dir.mkdir(parents=True)
    disk_payload = {
        "id": disk_job.id,
        "filename": disk_job.filename,
        "created_at": disk_job.created_at,
    }
    (disk_dir / "status.json").write_text(json.dumps(disk_payload), encoding="utf-8")

    corrupt_dir = tmp_path / "jobs" / "corrupt-job"
    corrupt_dir.mkdir()
    (corrupt_dir / "status.json").write_text("not-json", encoding="utf-8")

    listed = manager.list_jobs()
    assert [record.id for record in listed] == ["memory-job", "disk-job"]
    manager.shutdown()


def test_list_jobs_respects_limit(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    for index in range(3):
        record = JobRecord(id=f"job-{index}", filename="f.jpg", created_at=f"2024-01-0{index + 1}T00:00:00+00:00")
        manager._jobs[record.id] = record
    assert [record.id for record in manager.list_jobs(limit=2)] == ["job-2", "job-1"]
    manager.shutdown()
