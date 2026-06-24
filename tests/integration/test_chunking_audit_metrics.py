"""Integration tests for SETUP-08 audit + metrics + logs (T-S08-016)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from fe_bot.audit.service import AuditAction, InMemoryAuditLog
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry
from schemas.rag.ontology import (
    ConfidenceLevel,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)


def _setup_card(client, auth_headers, *, doc_id: str = "schema_card.audit.v1") -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Chunking Audit"},
        headers=auth_headers,
    )
    sid = resp.json()["setup_job_id"]
    from fe_bot.api.dependencies import get_card_registry as _get_reg

    registry: InMemoryRAGCardRegistry = client.app.dependency_overrides[_get_reg]()
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.SCHEMA_CARD,
        title="Audit",
        version="1.0",
        card_version="1.0",
        status=CardStatus.METADATA_VALIDATED,
        body_markdown="# Test\n\nBody",
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
    registry.add(setup_job_id=sid, card=card, metadata=meta)
    return sid


def test_run_writes_audit(
    client: TestClient,
    auth_headers: dict[str, str],
    audit_log: InMemoryAuditLog,
) -> None:
    sid = _setup_card(client, auth_headers)
    client.post(
        f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
    )
    actions = [e.action for e in audit_log.list_for_job(sid)]
    assert AuditAction.CHUNKING_RUN_TRIGGERED in actions
    assert AuditAction.CHUNKING_MANIFEST_CREATED in actions


def test_chunks_created_counter(
    client: TestClient,
    auth_headers: dict[str, str],
    metrics_registry: MetricsRegistry,
) -> None:
    metrics_registry.reset()
    sid = _setup_card(client, auth_headers, doc_id="schema_card.metric.v1")
    client.post(
        f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
    )
    assert (
        metrics_registry.counter_value(
            "chunks_created_total", labels={"chunk_type": "summary"}
        )
        == 1.0
    )


def test_runs_total_counter(
    client: TestClient,
    auth_headers: dict[str, str],
    metrics_registry: MetricsRegistry,
) -> None:
    metrics_registry.reset()
    sid = _setup_card(client, auth_headers, doc_id="schema_card.runs.v1")
    client.post(
        f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
    )
    assert (
        metrics_registry.counter_value(
            "chunking_runs_total", labels={"outcome": "completed"}
        )
        >= 1.0
    )


def test_card_duration_histogram(
    client: TestClient,
    auth_headers: dict[str, str],
    metrics_registry: MetricsRegistry,
) -> None:
    metrics_registry.reset()
    sid = _setup_card(client, auth_headers, doc_id="schema_card.dur.v1")
    client.post(
        f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
    )
    assert metrics_registry.histogram_count("chunking_card_duration_ms") >= 1


def test_structured_log(
    client: TestClient,
    auth_headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    sid = _setup_card(client, auth_headers, doc_id="schema_card.log.v1")
    with caplog.at_level(
        logging.INFO, logger="fe_bot.setup.chunking.orchestrator"
    ):
        client.post(
            f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
        )
    records = [r for r in caplog.records if r.message == "chunking_run_completed"]
    assert records, "expected chunking_run_completed log"
    rec = records[0]
    for attr in ("chunking_run_id", "manifest_id", "chunks_created", "outcome"):
        assert hasattr(rec, attr), f"missing {attr}"
