"""Unit tests for ValidationRunRepository (SETUP-07 / T-S07-005)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fe_bot.setup.metadata_validation.run_repository import (
    InMemoryValidationRunRepository,
    ValidationRunNotFoundError,
)
from schemas.setup.validation_run import ValidationRunDTO, ValidationRunStatus


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(rid: str = "run_1", setup_job_id: str = "sj1", **kw: object) -> ValidationRunDTO:
    defaults: dict[str, object] = {
        "validation_run_id": rid,
        "setup_job_id": setup_job_id,
        "status": ValidationRunStatus.RUNNING,
        "triggered_by": "u1",
        "policy": "strict",
        "started_at": _now(),
    }
    defaults.update(kw)
    return ValidationRunDTO(**defaults)  # type: ignore[arg-type]


def test_add_and_get():
    repo = InMemoryValidationRunRepository()
    r = _make()
    repo.add(r)
    assert repo.get("run_1").validation_run_id == "run_1"


def test_get_missing_raises():
    repo = InMemoryValidationRunRepository()
    with pytest.raises(ValidationRunNotFoundError):
        repo.get("missing")


def test_update_changes_status():
    repo = InMemoryValidationRunRepository()
    r = _make()
    repo.add(r)
    updated = r.model_copy(
        update={"status": ValidationRunStatus.COMPLETED, "finished_at": _now()}
    )
    repo.update(updated)
    got = repo.get("run_1")
    assert got.status == ValidationRunStatus.COMPLETED


def test_update_missing_raises():
    repo = InMemoryValidationRunRepository()
    r = _make()
    with pytest.raises(ValidationRunNotFoundError):
        repo.update(r)


def test_list_for_job_returns_in_order():
    repo = InMemoryValidationRunRepository()
    repo.add(_make("run_a"))
    repo.add(_make("run_b"))
    repo.add(_make("run_c", setup_job_id="sj2"))
    runs = repo.list_for_job("sj1")
    assert [r.validation_run_id for r in runs] == ["run_a", "run_b"]


def test_latest_for_job():
    repo = InMemoryValidationRunRepository()
    repo.add(_make("run_a"))
    repo.add(_make("run_b"))
    latest = repo.latest_for_job("sj1")
    assert latest is not None
    assert latest.validation_run_id == "run_b"


def test_latest_for_empty_job():
    repo = InMemoryValidationRunRepository()
    assert repo.latest_for_job("sj_empty") is None


def test_snapshot_restore_preserves_order():
    repo = InMemoryValidationRunRepository()
    repo.add(_make("run_a"))
    repo.add(_make("run_b"))
    data = repo.snapshot()

    repo2 = InMemoryValidationRunRepository()
    repo2.restore(data)
    latest = repo2.latest_for_job("sj1")
    assert latest is not None
    assert latest.validation_run_id == "run_b"
