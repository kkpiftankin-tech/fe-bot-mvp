"""Unit tests for ReviewDecisionDTO (SETUP-06 / T-S06-001)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.setup.review_decision import (
    RegenerateReason,
    RejectReason,
    ReviewDecision,
    ReviewDecisionDTO,
)


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(**overrides: object) -> ReviewDecisionDTO:
    defaults: dict[str, object] = {
        "review_decision_id": "rd_001",
        "setup_job_id": "setup_001",
        "doc_id": "schema.x.v1",
        "card_version": "1.0",
        "decision": ReviewDecision.APPROVE,
        "reviewer_id": "u1",
        "reviewer_role": "user",
        "created_at": _now(),
    }
    defaults.update(overrides)
    return ReviewDecisionDTO(**defaults)  # type: ignore[arg-type]


def test_all_review_decisions_present():
    expected = {
        "approve",
        "reject",
        "edit",
        "regenerate",
        "save_draft",
        "submit_edit",
        "request_changes",
        "defer",
    }
    assert {d.value for d in ReviewDecision} == expected


def test_all_reject_reasons_present():
    expected = {
        "duplicate",
        "wrong_doc_type",
        "incorrect_content",
        "irrelevant",
        "hallucination",
        "source_mismatch",
        "other",
    }
    assert {r.value for r in RejectReason} == expected


def test_all_regenerate_reasons_present():
    assert RegenerateReason.LOW_QUALITY.value == "low_quality"
    assert RegenerateReason.HALLUCINATION.value == "hallucination"


def test_approve_without_reason_ok():
    dto = _make(decision=ReviewDecision.APPROVE)
    assert dto.decision == ReviewDecision.APPROVE
    assert dto.reason is None


def test_approve_with_comment_ok():
    dto = _make(decision=ReviewDecision.APPROVE, comment="Looks correct")
    assert dto.comment == "Looks correct"


def test_reject_requires_reason():
    with pytest.raises(ValidationError) as exc_info:
        _make(decision=ReviewDecision.REJECT, reason=None)
    assert "REJECT_REASON_REQUIRED" in str(exc_info.value)


def test_reject_with_reason_ok():
    dto = _make(decision=ReviewDecision.REJECT, reason=RejectReason.DUPLICATE.value)
    assert dto.reason == "duplicate"


def test_regenerate_requires_reason():
    with pytest.raises(ValidationError) as exc_info:
        _make(decision=ReviewDecision.REGENERATE, reason=None)
    assert "REGENERATE_REASON_REQUIRED" in str(exc_info.value)


def test_dto_is_frozen():
    dto = _make()
    with pytest.raises(ValidationError):
        dto.comment = "mutated"  # type: ignore[misc]


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        _make(unknown_field="x")


def test_card_version_pattern_rejects_garbage():
    with pytest.raises(ValidationError):
        _make(card_version="vX")


def test_reviewer_id_required():
    with pytest.raises(ValidationError):
        _make(reviewer_id="")


def test_metadata_default_empty():
    dto = _make()
    assert dto.metadata == {}


def test_metadata_custom_payload():
    dto = _make(metadata={"client_ip": "10.0.0.1", "ui": "web"})
    assert dto.metadata["client_ip"] == "10.0.0.1"
