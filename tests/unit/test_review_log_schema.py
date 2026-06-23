"""Unit tests for ReviewLogDTO (SETUP-06 / T-S06-002)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.setup.review_log import ReviewLogDTO, ReviewLogEventType


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(**overrides: object) -> ReviewLogDTO:
    defaults: dict[str, object] = {
        "review_log_id": "rl_001",
        "setup_job_id": "setup_001",
        "doc_id": "schema.x.v1",
        "card_version": "1.0",
        "event_type": ReviewLogEventType.APPROVED,
        "actor_id": "u1",
        "actor_role": "user",
        "message": "Approved by reviewer",
        "before_status": "review_required",
        "after_status": "approved",
        "created_at": _now(),
    }
    defaults.update(overrides)
    return ReviewLogDTO(**defaults)  # type: ignore[arg-type]


def test_all_event_types_present():
    expected = {
        "review_started",
        "approved",
        "rejected",
        "edited",
        "regenerate_requested",
        "version_created",
        "review_completed",
        "edit_lock_acquired",
        "edit_lock_released",
    }
    assert {e.value for e in ReviewLogEventType} == expected


def test_approve_log_entry():
    log = _make(event_type=ReviewLogEventType.APPROVED)
    assert log.event_type == ReviewLogEventType.APPROVED
    assert log.before_status == "review_required"
    assert log.after_status == "approved"


def test_dto_is_frozen():
    log = _make()
    with pytest.raises(ValidationError):
        log.message = "mutated"  # type: ignore[misc]


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        _make(unknown="x")


def test_message_required_non_empty():
    with pytest.raises(ValidationError):
        _make(message="")


def test_message_too_long_rejected():
    with pytest.raises(ValidationError):
        _make(message="x" * 4001)


def test_before_after_status_optional():
    log = _make(
        event_type=ReviewLogEventType.REVIEW_STARTED,
        before_status=None,
        after_status=None,
    )
    assert log.before_status is None
    assert log.after_status is None


def test_payload_default_empty():
    log = _make()
    assert log.payload == {}


def test_payload_custom():
    log = _make(payload={"review_decision_id": "rd_001", "duration_ms": 42})
    assert log.payload["duration_ms"] == 42


def test_card_version_pattern():
    with pytest.raises(ValidationError):
        _make(card_version="latest")
