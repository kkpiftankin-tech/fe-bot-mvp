"""Unit tests for ValidationRunDTO (SETUP-07 / T-S07-001)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.validation_run import ValidationRunDTO, ValidationRunStatus


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(**kw: object) -> ValidationRunDTO:
    defaults: dict[str, object] = {
        "validation_run_id": "vr_001",
        "setup_job_id": "sj1",
        "status": ValidationRunStatus.RUNNING,
        "triggered_by": "u1",
        "policy": "strict",
        "started_at": _now(),
    }
    defaults.update(kw)
    return ValidationRunDTO(**defaults)  # type: ignore[arg-type]


def test_all_statuses():
    assert {s.value for s in ValidationRunStatus} == {
        "created",
        "running",
        "completed",
        "failed",
    }


def test_default_counts_zero():
    r = _make()
    assert r.total == 0
    assert r.passed == 0
    assert r.duration_ms is None


def test_completed_requires_finished_at():
    with pytest.raises(ValidationError):
        _make(status=ValidationRunStatus.COMPLETED)


def test_completed_with_finished_at_ok():
    r = _make(
        status=ValidationRunStatus.COMPLETED,
        finished_at=_now(),
        total=5,
        passed=3,
        warnings=1,
        failed=1,
        duration_ms=120,
    )
    assert r.status == ValidationRunStatus.COMPLETED


def test_frozen():
    r = _make()
    with pytest.raises(ValidationError):
        r.total = 10  # type: ignore[misc]


def test_negative_counts_rejected():
    with pytest.raises(ValidationError):
        _make(total=-1)


def test_error_message_for_failed():
    r = _make(status=ValidationRunStatus.FAILED, error_message="LLM down")
    assert r.error_message == "LLM down"
