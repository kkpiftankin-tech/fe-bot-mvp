"""Component tests for SETUP-08 ChunkingOrchestrator (T-S08-006)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fe_bot.audit.service import AuditAction, AuditService, InMemoryAuditLog
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry
from fe_bot.setup.chunking.events import EVENT_RUN_COMPLETED, EVENT_RUN_STARTED
from fe_bot.setup.chunking.manifest_repository import (
    InMemoryChunkManifestRepository,
)
from fe_bot.setup.chunking.metrics import ChunkingMetricsCollector
from fe_bot.setup.chunking.orchestrator import ChunkingOrchestrator
from fe_bot.setup.chunking.service import ChunkingService
from fe_bot.setup.events import EventBus
from schemas.rag.ontology import (
    ConfidenceLevel,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata

pytestmark = pytest.mark.component


def _now() -> datetime:
    return datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)


def _make_pair(
    *,
    doc_id: str = "schema_card.test.v1",
    status: CardStatus = CardStatus.METADATA_VALIDATED,
) -> tuple[RAGCard, RAGMetadata]:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.SCHEMA_CARD,
        title="Test",
        version="1.0",
        card_version="1.0",
        status=status,
        body_markdown="# Test\n\nValid body content for chunking",
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
        doc_type=DocType.SCHEMA_CARD,
        phase=[Phase.FEATURE_SYNTHESIS],
        domain=[Domain.NAVAL],
        task_type=[TaskType.CLASSIFICATION],
        retrieval_tags=["test"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


@pytest.fixture
def orch_bundle() -> dict[str, object]:
    registry = InMemoryRAGCardRegistry()
    manifest_repo = InMemoryChunkManifestRepository()
    audit_log = InMemoryAuditLog()
    audit = AuditService(audit_log)
    metrics = MetricsRegistry()
    bus = EventBus()
    events: list[object] = []
    bus.subscribe(events.append)
    orch = ChunkingOrchestrator(
        registry=registry,
        chunking=ChunkingService(),
        manifest_repo=manifest_repo,
        event_bus=bus,
        audit_service=audit,
        metrics=ChunkingMetricsCollector(metrics=metrics),
    )
    return {
        "orch": orch,
        "registry": registry,
        "manifest_repo": manifest_repo,
        "audit_log": audit_log,
        "metrics": metrics,
        "events": events,
    }


def test_run_for_job_persists_manifest(orch_bundle):
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    run = orch_bundle["orch"].run_for_job("sj1", triggered_by="u1")
    assert run.total_cards == 1
    assert run.chunks_created == 3  # summary + definition + metadata_summary
    manifest = orch_bundle["manifest_repo"].get_latest_for_job("sj1")
    assert manifest is not None
    assert manifest.total_chunks == 3
    assert manifest.by_type["summary"] == 1


def test_run_transitions_card_to_chunked(orch_bundle):
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    orch_bundle["orch"].run_for_job("sj1", triggered_by="u1")
    rec = orch_bundle["registry"].get("schema_card.test.v1")
    # APPROVED is not in valid transitions to CHUNKED directly — but
    # METADATA_VALIDATED → CHUNKED ok.
    assert rec.card.status == CardStatus.CHUNKED


def test_run_audit(orch_bundle):
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    orch_bundle["orch"].run_for_job("sj1", triggered_by="u1")
    actions = [e.action for e in orch_bundle["audit_log"].list_for_job("sj1")]
    assert AuditAction.CHUNKING_RUN_TRIGGERED in actions
    assert AuditAction.CHUNKING_MANIFEST_CREATED in actions


def test_run_events(orch_bundle):
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    orch_bundle["orch"].run_for_job("sj1", triggered_by="u1")
    event_types = [getattr(e, "event_type", None) for e in orch_bundle["events"]]
    assert EVENT_RUN_STARTED in event_types
    assert EVENT_RUN_COMPLETED in event_types


def test_run_metrics(orch_bundle):
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    orch_bundle["orch"].run_for_job("sj1", triggered_by="u1")
    m: MetricsRegistry = orch_bundle["metrics"]
    assert m.counter_value("chunking_runs_total", labels={"outcome": "completed"}) == 1.0
    assert m.counter_value("chunks_created_total", labels={"chunk_type": "summary"}) == 1.0


def test_preview_does_not_persist(orch_bundle):
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    chunks = orch_bundle["orch"].preview_card("schema_card.test.v1")
    assert len(chunks) == 3
    # No manifest saved
    assert orch_bundle["manifest_repo"].get_latest_for_job("sj1") is None


def test_refresh_saves_new_manifest(orch_bundle):
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    chunks = orch_bundle["orch"].refresh_card(
        "schema_card.test.v1", triggered_by="u1"
    )
    assert len(chunks) == 3
    manifest = orch_bundle["manifest_repo"].get_latest_for_job("sj1")
    assert manifest is not None


def test_run_ignores_non_eligible_cards(orch_bundle):
    card, meta = _make_pair(status=CardStatus.REVIEW_REQUIRED)
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    run = orch_bundle["orch"].run_for_job("sj1", triggered_by="u1")
    assert run.total_cards == 0
    assert run.chunks_created == 0


def test_chunk_id_stability(orch_bundle):
    """AC-01: повторный run даёт те же chunk_id."""
    card, meta = _make_pair()
    orch_bundle["registry"].add(setup_job_id="sj1", card=card, metadata=meta)
    chunks1 = orch_bundle["orch"].preview_card("schema_card.test.v1")
    chunks2 = orch_bundle["orch"].preview_card("schema_card.test.v1")
    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]
