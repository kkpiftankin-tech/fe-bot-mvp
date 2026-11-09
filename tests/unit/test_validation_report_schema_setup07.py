"""Unit tests for ValidationReport SETUP-07 extension (T-S07-002)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.validation_report import (
    ValidationReport,
    ValidationStatus,
    ValidationTargetType,
)


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(**kw: object) -> ValidationReport:
    defaults: dict[str, object] = {
        "validation_report_id": "vr_001",
        "target_type": ValidationTargetType.RAG_CARD,
        "target_id": "schema.x.v1",
        "status": ValidationStatus.PASSED,
        "created_at": _now(),
        "validator_name": "rag_metadata_validator",
    }
    defaults.update(kw)
    return ValidationReport(**defaults)  # type: ignore[arg-type]


def test_minimal_without_setup07_fields():
    """Backward compatibility: report без setup-07 полей всё ещё валиден."""
    r = _make()
    assert r.setup_job_id is None
    assert r.card_version is None
    assert r.policy_used is None
    assert r.validation_run_id is None


def test_with_setup07_fields():
    r = _make(
        setup_job_id="sj1",
        card_version="1.0",
        policy_used="strict",
        validation_run_id="vr_001",
    )
    assert r.setup_job_id == "sj1"
    assert r.card_version == "1.0"
    assert r.policy_used == "strict"
    assert r.validation_run_id == "vr_001"


def test_card_version_pattern_rejects_garbage():
    with pytest.raises(ValidationError):
        _make(card_version="latest")


def test_card_version_accepts_two_three_segment():
    _make(card_version="1.0")
    _make(card_version="2.0.1")


def test_is_passing_property():
    assert _make(status=ValidationStatus.PASSED).is_passing
    assert _make(status=ValidationStatus.WARNING).is_passing
    assert not _make(status=ValidationStatus.FAILED).is_passing
    assert not _make(status=ValidationStatus.REPAIR_REQUIRED).is_passing
