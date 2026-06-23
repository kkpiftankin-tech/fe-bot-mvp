"""Unit tests for SETUP-06 review events (T-S06-019)."""

from __future__ import annotations

from datetime import UTC, datetime

from fe_bot.setup.card_review.events import (
    EVENT_APPROVED,
    EVENT_EDITED,
    EVENT_READINESS_CHANGED,
    EVENT_REGENERATE_REQUESTED,
    EVENT_REJECTED,
    EVENT_REVIEW_COMPLETED,
    EVENT_REVIEW_STARTED,
    EVENT_VERSION_CREATED,
    RAGCardApprovedEvent,
    RAGCardEditedEvent,
    RAGCardRegenerateRequestedEvent,
    RAGCardRejectedEvent,
    RAGCardReviewCompletedEvent,
    RAGCardReviewStartedEvent,
    RAGCardVersionCreatedEvent,
    SetupReviewReadinessChangedEvent,
    event_payload,
    event_type_of,
)


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def test_approved_event_type():
    event = RAGCardApprovedEvent(
        event_id="evt_1",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        card_version="1.0",
        review_decision_id="rd1",
        reviewer_id="u1",
        duration_ms=42,
    )
    assert event_type_of(event) == EVENT_APPROVED


def test_rejected_event_type():
    event = RAGCardRejectedEvent(
        event_id="evt_2",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        card_version="1.0",
        review_decision_id="rd2",
        reviewer_id="u1",
        reason="duplicate",
    )
    assert event_type_of(event) == EVENT_REJECTED


def test_edited_event_type():
    event = RAGCardEditedEvent(
        event_id="evt_3",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        previous_card_version="1.0",
        new_card_version="1.1",
        reviewer_id="u1",
        metadata_changed=True,
        body_changed=False,
    )
    assert event_type_of(event) == EVENT_EDITED


def test_version_created_event():
    event = RAGCardVersionCreatedEvent(
        event_id="evt_4",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        card_version="1.1",
        parent_card_version="1.0",
        created_by="u1",
        change_reason="fix typo",
    )
    assert event_type_of(event) == EVENT_VERSION_CREATED


def test_regenerate_requested_event():
    event = RAGCardRegenerateRequestedEvent(
        event_id="evt_5",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        card_version="1.0",
        regenerate_request_id="rg1",
        generation_job_id="gen1",
        reviewer_id="u1",
        reason="low_quality",
    )
    assert event_type_of(event) == EVENT_REGENERATE_REQUESTED


def test_review_started_event():
    event = RAGCardReviewStartedEvent(
        event_id="evt_6",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        card_version="1.0",
        reviewer_id="u1",
    )
    assert event_type_of(event) == EVENT_REVIEW_STARTED


def test_review_completed_event():
    event = RAGCardReviewCompletedEvent(
        event_id="evt_7",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        card_version="1.0",
        final_status="approved",
        reviewer_id="u1",
    )
    assert event_type_of(event) == EVENT_REVIEW_COMPLETED


def test_readiness_changed_event():
    event = SetupReviewReadinessChangedEvent(
        event_id="evt_8",
        setup_job_id="sj1",
        occurred_at=_now(),
        total=10,
        approved=8,
        rejected=1,
        blocking=1,
        ready_for_next_step=False,
    )
    assert event_type_of(event) == EVENT_READINESS_CHANGED


def test_event_payload_serializable():
    event = RAGCardApprovedEvent(
        event_id="evt_a",
        setup_job_id="sj1",
        occurred_at=_now(),
        doc_id="d1",
        card_version="1.0",
        review_decision_id="rd1",
        reviewer_id="u1",
        duration_ms=100,
    )
    payload = event_payload(event)
    assert payload["doc_id"] == "d1"
    assert payload["duration_ms"] == 100
