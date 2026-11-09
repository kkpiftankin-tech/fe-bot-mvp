"""Unit tests for ValidationReportRepository (SETUP-07 / T-S07-004)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.validation_report import (
    ValidationReport,
    ValidationStatus,
    ValidationTargetType,
)

from fe_bot.setup.metadata_validation.report_repository import (
    InMemoryValidationReportRepository,
    ValidationReportNotFoundError,
)


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(rid: str = "vr_1", **kw: object) -> ValidationReport:
    defaults: dict[str, object] = {
        "validation_report_id": rid,
        "target_type": ValidationTargetType.RAG_CARD,
        "target_id": "schema.x.v1",
        "status": ValidationStatus.PASSED,
        "created_at": _now(),
        "validator_name": "v1",
        "setup_job_id": "sj1",
        "card_version": "1.0",
    }
    defaults.update(kw)
    return ValidationReport(**defaults)  # type: ignore[arg-type]


def test_save_and_get():
    repo = InMemoryValidationReportRepository()
    r = _make()
    repo.save(r)
    assert repo.get("vr_1").validation_report_id == "vr_1"


def test_get_missing_raises():
    repo = InMemoryValidationReportRepository()
    with pytest.raises(ValidationReportNotFoundError):
        repo.get("missing")


def test_get_latest_returns_most_recent():
    repo = InMemoryValidationReportRepository()
    repo.save(_make(rid="vr_1"))
    repo.save(_make(rid="vr_2"))
    latest = repo.get_latest("sj1", "schema.x.v1")
    assert latest is not None
    assert latest.validation_report_id == "vr_2"


def test_get_latest_returns_none_when_no_reports():
    repo = InMemoryValidationReportRepository()
    assert repo.get_latest("sj1", "schema.x.v1") is None


def test_list_for_job_filters():
    repo = InMemoryValidationReportRepository()
    repo.save(_make(rid="vr_1", setup_job_id="sj1"))
    repo.save(_make(rid="vr_2", setup_job_id="sj2"))
    repo.save(_make(rid="vr_3", setup_job_id="sj1"))
    assert len(repo.list_for_job("sj1")) == 2


def test_list_for_card_filters():
    repo = InMemoryValidationReportRepository()
    repo.save(_make(rid="vr_1", target_id="a.v1"))
    repo.save(_make(rid="vr_2", target_id="b.v1"))
    repo.save(_make(rid="vr_3", target_id="a.v1"))
    items = repo.list_for_card("sj1", "a.v1")
    assert {r.validation_report_id for r in items} == {"vr_1", "vr_3"}


def test_list_for_run():
    repo = InMemoryValidationReportRepository()
    repo.save(_make(rid="vr_1", validation_run_id="run_a"))
    repo.save(_make(rid="vr_2", validation_run_id="run_a"))
    repo.save(_make(rid="vr_3", validation_run_id="run_b"))
    assert len(repo.list_for_run("run_a")) == 2


def test_snapshot_restore_roundtrip():
    repo = InMemoryValidationReportRepository()
    repo.save(_make(rid="vr_1"))
    repo.save(_make(rid="vr_2"))
    data = repo.snapshot()

    repo2 = InMemoryValidationReportRepository()
    repo2.restore(data)
    assert repo2.get("vr_1").validation_report_id == "vr_1"
    latest = repo2.get_latest("sj1", "schema.x.v1")
    assert latest is not None
    assert latest.validation_report_id == "vr_2"
