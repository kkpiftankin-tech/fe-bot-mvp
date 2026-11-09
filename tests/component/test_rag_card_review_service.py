"""Component tests for new RAGCardReviewService (SETUP-06 / T-S06-020)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from schemas.rag.ontology import (
    ConfidenceLevel,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata

from fe_bot.audit.service import AuditAction, AuditService, InMemoryAuditLog
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry
from fe_bot.setup.card_review.decision_repository import (
    InMemoryReviewDecisionRepository,
)
from fe_bot.setup.card_review.edit_lock_repository import InMemoryEditLockRepository
from fe_bot.setup.card_review.events import EVENT_APPROVED, EVENT_REJECTED
from fe_bot.setup.card_review.log_repository import InMemoryReviewLogRepository
from fe_bot.setup.card_review.metrics import ReviewMetricsCollector
from fe_bot.setup.card_review.readiness import ReviewReadinessCalculator
from fe_bot.setup.card_review.service import (
    CardHasCriticalValidationErrorsError,
    CardVersionConflictError,
    InvalidEditPayloadError,
    Pagination,
    RAGCardReviewService,
    ReviewListFilters,
)
from fe_bot.setup.card_review.version_repository import (
    InMemoryRAGCardVersionRepository,
)
from fe_bot.setup.events import EventBus

pytestmark = pytest.mark.component


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make_pair(
    *,
    doc_id: str = "analytics_card.test.v1",
    status: CardStatus = CardStatus.REVIEW_REQUIRED,
    body: str = "# Test\n\nThis is a sufficiently long body for validation",
    confidence: str = "high",
) -> tuple[RAGCard, RAGMetadata]:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        title="Test card",
        version="1.0",
        card_version="1.0",
        status=status,
        body_markdown=body,
        source_document_ids=["src_1"],
        source_section_ids=["sec_1"],
        primary_source_section_id="sec_1",
        confidence_level=confidence,
        created_by="generator",
        created_at=_now(),
        updated_at=_now(),
    )
    meta = RAGMetadata(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        phase=[Phase.FEATURE_SYNTHESIS],
        domain=[Domain.NAVAL],
        task_type=[TaskType.CLASSIFICATION],
        retrieval_tags=["test"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


@pytest.fixture
def full_service() -> dict[str, Any]:
    registry = InMemoryRAGCardRegistry()
    decisions = InMemoryReviewDecisionRepository()
    logs = InMemoryReviewLogRepository()
    versions = InMemoryRAGCardVersionRepository()
    edit_locks = InMemoryEditLockRepository()
    audit_log = InMemoryAuditLog()
    audit = AuditService(audit_log)
    metrics = MetricsRegistry()
    review_metrics = ReviewMetricsCollector(metrics=metrics)
    readiness = ReviewReadinessCalculator(card_registry=registry)
    bus = EventBus()
    events_received: list[Any] = []
    bus.subscribe(events_received.append)
    svc = RAGCardReviewService(
        registry,
        decision_repo=decisions,
        log_repo=logs,
        version_repo=versions,
        edit_lock_repo=edit_locks,
        readiness_calculator=readiness,
        event_bus=bus,
        audit_service=audit,
        metrics=review_metrics,
    )
    return {
        "svc": svc,
        "registry": registry,
        "decisions": decisions,
        "logs": logs,
        "versions": versions,
        "audit_log": audit_log,
        "metrics": metrics,
        "events": events_received,
    }


# ============================================================
# approve_card
# ============================================================


def test_approve_card_happy(full_service):
    svc = full_service["svc"]
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    record = svc.approve_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        comment="ok",
    )
    assert record.card.status == CardStatus.APPROVED
    assert record.card.reviewed_by == "u1"


def test_approve_records_decision_and_log(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    full_service["svc"].approve_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        review_decision_id="rd_001",
    )
    assert full_service["decisions"].exists("rd_001")
    assert full_service["logs"].count_for_card("analytics_card.test.v1") >= 1


def test_approve_blocked_by_pre_approve(full_service):
    card, meta = _make_pair(body="short")
    full_service["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    with pytest.raises(CardHasCriticalValidationErrorsError):
        full_service["svc"].approve_card(
            doc_id="analytics_card.test.v1",
            reviewer_id="u1",
        )


def test_approve_idempotent(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    r1 = full_service["svc"].approve_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        review_decision_id="rd_xyz",
        comment="first",
    )
    r2 = full_service["svc"].approve_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u2",  # different user — should be ignored
        review_decision_id="rd_xyz",
        comment="second",
    )
    assert r1.card.status == r2.card.status == CardStatus.APPROVED
    # Только одна decision записана.
    decisions = full_service["decisions"].list_for_card("analytics_card.test.v1")
    assert len(decisions) == 1
    assert decisions[0].reviewer_id == "u1"


def test_approve_emits_event(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    full_service["svc"].approve_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
    )
    event_types = [
        getattr(e, "event_type", None) for e in full_service["events"]
    ]
    assert EVENT_APPROVED in event_types


def test_approve_writes_audit(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    full_service["svc"].approve_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
    )
    audit_events = full_service["audit_log"].list_for_job("sj1")
    assert any(e.action == AuditAction.CARD_REVIEW_APPROVED for e in audit_events)


def test_approve_metrics_counter(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    full_service["svc"].approve_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
    )
    metrics: MetricsRegistry = full_service["metrics"]
    assert (
        metrics.counter_value("rag_card_reviews_total", labels={"decision": "approve"})
        == 1.0
    )


# ============================================================
# reject_card
# ============================================================


def test_reject_card_happy(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    record = full_service["svc"].reject_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        reason="duplicate",
    )
    assert record.card.status == CardStatus.REJECTED


def test_reject_requires_reason(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    with pytest.raises(InvalidEditPayloadError):
        full_service["svc"].reject_card(
            doc_id="analytics_card.test.v1",
            reviewer_id="u1",
            reason="",
        )


def test_reject_emits_event(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    full_service["svc"].reject_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        reason="hallucination",
    )
    event_types = [getattr(e, "event_type", None) for e in full_service["events"]]
    assert EVENT_REJECTED in event_types


# ============================================================
# edit_card
# ============================================================


def test_edit_creates_new_version(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    record = full_service["svc"].edit_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        metadata_patch={"title": "Updated Title"},
        change_reason="typo fix",
    )
    assert record.card.title == "Updated Title"
    assert record.card.card_version == "1.1"  # minor bump


def test_edit_version_conflict(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    with pytest.raises(CardVersionConflictError):
        full_service["svc"].edit_card(
            doc_id="analytics_card.test.v1",
            reviewer_id="u1",
            expected_version="0.9",
            metadata_patch={"title": "X"},
        )


def test_edit_rejects_system_metadata(full_service):
    from fe_bot.setup.card_review.editor import SystemMetadataReadOnlyError

    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    with pytest.raises(SystemMetadataReadOnlyError):
        full_service["svc"].edit_card(
            doc_id="analytics_card.test.v1",
            reviewer_id="u1",
            metadata_patch={"doc_id": "new.id"},
        )


def test_edit_records_version_in_repo(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    full_service["svc"].edit_card(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        metadata_patch={"title": "X"},
        change_reason="test",
    )
    versions = full_service["versions"].list_for_card("analytics_card.test.v1")
    assert any(v.card_version == "1.1" for v in versions)


# ============================================================
# request_regeneration
# ============================================================


def test_regenerate_requires_reason(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    with pytest.raises(InvalidEditPayloadError):
        full_service["svc"].request_regeneration(
            doc_id="analytics_card.test.v1",
            reviewer_id="u1",
            reason="",
        )


def test_regenerate_sets_status(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    record = full_service["svc"].request_regeneration(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        reason="low_quality",
    )
    assert record.card.status == CardStatus.REGENERATE_REQUESTED


def test_regenerate_records_decision(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    full_service["svc"].request_regeneration(
        doc_id="analytics_card.test.v1",
        reviewer_id="u1",
        reason="low_quality",
        regenerate_request_id="rg_001",
    )
    assert full_service["decisions"].exists("rg_001")


# ============================================================
# bulk_approve
# ============================================================


def test_bulk_approve_happy(full_service):
    for i in range(3):
        card, meta = _make_pair(doc_id=f"c.v{i}")
        full_service["registry"].add(setup_job_id="sj1", card=card, metadata=meta)

    result = full_service["svc"].bulk_approve_cards(
        setup_job_id="sj1",
        reviewer_id="u1",
        items=[(f"c.v{i}", "1.0") for i in range(3)],
    )
    assert result["approved"] == 3
    assert result["errors"] == 0


def test_bulk_approve_partial(full_service):
    # Card 0 - approvable
    card_ok, meta_ok = _make_pair(doc_id="ok.v1")
    full_service["registry"].add(setup_job_id="sj1", card=card_ok, metadata=meta_ok)
    # Card 1 - too short body
    card_bad, meta_bad = _make_pair(doc_id="bad.v1", body="short")
    full_service["registry"].add(
        setup_job_id="sj1", card=card_bad, metadata=meta_bad
    )

    result = full_service["svc"].bulk_approve_cards(
        setup_job_id="sj1",
        reviewer_id="u1",
        items=[("ok.v1", "1.0"), ("bad.v1", "1.0")],
    )
    assert result["approved"] == 1
    assert result["errors"] == 1


# ============================================================
# list / details
# ============================================================


def test_list_review_cards(full_service):
    for i in range(5):
        card, meta = _make_pair(doc_id=f"c.v{i}")
        full_service["registry"].add(setup_job_id="sj1", card=card, metadata=meta)

    resp = full_service["svc"].list_review_cards("sj1")
    assert resp.total == 5
    assert len(resp.items) == 5


def test_list_with_filter_status(full_service):
    card1, meta1 = _make_pair(doc_id="c1", status=CardStatus.REVIEW_REQUIRED)
    card2, meta2 = _make_pair(doc_id="c2", status=CardStatus.APPROVED)
    full_service["registry"].add(setup_job_id="sj1", card=card1, metadata=meta1)
    full_service["registry"].add(setup_job_id="sj1", card=card2, metadata=meta2)

    resp = full_service["svc"].list_review_cards(
        "sj1", filters=ReviewListFilters(status="review_required")
    )
    assert resp.total == 1
    assert resp.items[0].doc_id == "c1"


def test_list_with_pagination(full_service):
    for i in range(10):
        card, meta = _make_pair(doc_id=f"c{i}.v1")
        full_service["registry"].add(setup_job_id="sj1", card=card, metadata=meta)

    resp = full_service["svc"].list_review_cards(
        "sj1", pagination=Pagination(page=2, page_size=3)
    )
    assert len(resp.items) == 3
    assert resp.total == 10


def test_get_card_for_review(full_service):
    full_service["registry"].add(
        setup_job_id="sj1", card=_make_pair()[0], metadata=_make_pair()[1]
    )
    details = full_service["svc"].get_card_for_review("analytics_card.test.v1")
    assert details.doc_id == "analytics_card.test.v1"
    assert details.permissions["can_approve"] is True


def test_get_card_for_review_low_confidence_warning(full_service):
    card, meta = _make_pair(confidence="low")
    full_service["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    details = full_service["svc"].get_card_for_review("analytics_card.test.v1")
    warning_codes = {w["code"] for w in details.validation["warnings"]}
    assert "LOW_CONFIDENCE_APPROVE" in warning_codes
