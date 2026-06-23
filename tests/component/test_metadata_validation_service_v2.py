"""Component tests for SETUP-07 enhanced MetadataValidationService (T-S07-008)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fe_bot.audit.service import AuditAction, AuditService, InMemoryAuditLog
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry
from fe_bot.setup.events import EventBus
from fe_bot.setup.metadata_validation.events import (
    EVENT_REPORT_CREATED,
    EVENT_RUN_COMPLETED,
    EVENT_RUN_STARTED,
)
from fe_bot.setup.metadata_validation.metrics import ValidationMetricsCollector
from fe_bot.setup.metadata_validation.report_repository import (
    InMemoryValidationReportRepository,
)
from fe_bot.setup.metadata_validation.run_repository import (
    InMemoryValidationRunRepository,
)
from fe_bot.setup.metadata_validation.service import (
    MetadataValidationService,
    ReviewPolicy,
)
from schemas.rag.ontology import (
    ConfidenceLevel,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata
from schemas.setup.validation_run import ValidationRunStatus

pytestmark = pytest.mark.component


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make_pair(
    *,
    doc_id: str = "analytics_card.test.v1",
    status: CardStatus = CardStatus.APPROVED,
    body: str = "# Test\n\nValid body content here",
    retrieval_tags: list[str] | None = None,
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
        confidence_level="high",
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
        retrieval_tags=retrieval_tags if retrieval_tags is not None else ["test"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


@pytest.fixture
def svc_bundle() -> dict[str, object]:
    registry = InMemoryRAGCardRegistry()
    reports = InMemoryValidationReportRepository()
    runs = InMemoryValidationRunRepository()
    audit_log = InMemoryAuditLog()
    audit = AuditService(audit_log)
    metrics = MetricsRegistry()
    val_metrics = ValidationMetricsCollector(metrics=metrics)
    bus = EventBus()
    events: list[object] = []
    bus.subscribe(events.append)
    svc = MetadataValidationService(
        registry=registry,
        review_policy=ReviewPolicy.STRICT,
        report_repo=reports,
        run_repo=runs,
        event_bus=bus,
        audit_service=audit,
        metrics=val_metrics,
    )
    return {
        "svc": svc,
        "registry": registry,
        "reports": reports,
        "runs": runs,
        "audit_log": audit_log,
        "metrics": metrics,
        "events": events,
    }


def test_validate_for_job_persists_reports(svc_bundle):
    card, meta = _make_pair()
    svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    result = svc_bundle["svc"].validate_for_job("sj1", triggered_by="u1")
    assert result.total == 1
    persisted = svc_bundle["reports"].list_for_job("sj1")
    assert len(persisted) == 1
    assert persisted[0].setup_job_id == "sj1"


def test_validate_for_job_creates_run(svc_bundle):
    card, meta = _make_pair()
    svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    svc_bundle["svc"].validate_for_job("sj1", triggered_by="u1")
    runs = svc_bundle["runs"].list_for_job("sj1")
    assert len(runs) == 1
    assert runs[0].status == ValidationRunStatus.COMPLETED
    assert runs[0].triggered_by == "u1"


def test_validate_for_job_writes_audit(svc_bundle):
    card, meta = _make_pair()
    svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    svc_bundle["svc"].validate_for_job("sj1", triggered_by="u1")
    actions = [e.action for e in svc_bundle["audit_log"].list_for_job("sj1")]
    assert AuditAction.VALIDATION_RUN_TRIGGERED in actions
    assert AuditAction.VALIDATION_REPORT_CREATED in actions


def test_validate_for_job_emits_events(svc_bundle):
    card, meta = _make_pair()
    svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    svc_bundle["svc"].validate_for_job("sj1", triggered_by="u1")
    event_types = [getattr(e, "event_type", None) for e in svc_bundle["events"]]
    assert EVENT_RUN_STARTED in event_types
    assert EVENT_REPORT_CREATED in event_types
    assert EVENT_RUN_COMPLETED in event_types


def test_validate_for_job_metrics(svc_bundle):
    card, meta = _make_pair()
    svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    svc_bundle["svc"].validate_for_job("sj1", triggered_by="u1")
    metrics: MetricsRegistry = svc_bundle["metrics"]
    assert metrics.counter_value("validation_runs_total", labels={"outcome": "completed"}) >= 1.0


def test_get_summary_aggregates_latest(svc_bundle):
    for i in range(3):
        card, meta = _make_pair(doc_id=f"c{i}.v1")
        svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    svc_bundle["svc"].validate_for_job("sj1", triggered_by="u1")
    summary = svc_bundle["svc"].get_summary("sj1")
    assert summary.total == 3
    assert summary.setup_job_id == "sj1"


def test_validate_one_persists_report(svc_bundle):
    card, meta = _make_pair(doc_id="single.v1")
    svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    report = svc_bundle["svc"].validate_one("single.v1", triggered_by="u1")
    assert report.target_id == "single.v1"
    latest = svc_bundle["reports"].get_latest("sj1", "single.v1")
    assert latest is not None
    assert latest.validation_report_id == report.validation_report_id


def test_validate_one_no_repos_fallback():
    """Backward compat: сервис без SETUP-07 deps работает как legacy."""
    registry = InMemoryRAGCardRegistry()
    svc = MetadataValidationService(registry=registry)
    card, meta = _make_pair(doc_id="legacy.v1")
    registry.add(setup_job_id="sj1", card=card, metadata=meta)
    report = svc.validate_one("legacy.v1")
    assert report.target_id == "legacy.v1"


def test_eligible_includes_approved(svc_bundle):
    """SETUP-07 расширение: APPROVED + READY_FOR_METADATA_VALIDATION тоже валидируются."""
    card, meta = _make_pair(doc_id="approved.v1", status=CardStatus.APPROVED)
    svc_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    result = svc_bundle["svc"].validate_for_job("sj1", triggered_by="u1")
    assert result.total == 1
