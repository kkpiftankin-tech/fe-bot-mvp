"""Integration tests for SETUP-06 audit + metrics + structured logs (T-S06-037..039)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from schemas.rag.ontology import (
    ConfidenceLevel,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata

from fe_bot.audit.service import AuditAction, InMemoryAuditLog
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _setup_card(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    doc_id: str = "schema_card.audit.v1",
) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Audit"},
        headers=auth_headers,
    )
    sid = resp.json()["setup_job_id"]
    from fe_bot.api.dependencies import get_card_registry as _get_reg

    registry: InMemoryRAGCardRegistry = client.app.dependency_overrides[_get_reg]()
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.SCHEMA_CARD,
        title="Audit card",
        version="1.0",
        card_version="1.0",
        status=CardStatus.REVIEW_REQUIRED,
        body_markdown="# Test\n\nSome sufficiently long body content here",
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


class TestAudit:
    def test_approve_writes_audit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _setup_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.audit.v1/review",
            json={"decision": "approve"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        events = audit_log.list_for_job(sid)
        assert any(e.action == AuditAction.CARD_REVIEW_APPROVED for e in events)

    def test_reject_writes_audit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _setup_card(client, auth_headers, doc_id="schema_card.reject.v1")
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.reject.v1/review",
            json={"decision": "reject", "reason": "duplicate"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        events = audit_log.list_for_job(sid)
        assert any(e.action == AuditAction.CARD_REVIEW_REJECTED for e in events)

    def test_edit_writes_audit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _setup_card(client, auth_headers, doc_id="schema_card.edit.v1")
        r = client.patch(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.edit.v1",
            json={
                "expected_version": "1.0",
                "metadata_patch": {"title": "New"},
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        events = audit_log.list_for_job(sid)
        assert any(e.action == AuditAction.CARD_REVIEW_EDITED for e in events)


class TestMetrics:
    def test_approve_counter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _setup_card(client, auth_headers, doc_id="schema_card.metric.v1")
        client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.metric.v1/review",
            json={"decision": "approve"},
            headers=auth_headers,
        )
        v = metrics_registry.counter_value(
            "rag_card_reviews_total", labels={"decision": "approve"}
        )
        assert v == 1.0

    def test_rejected_counter_per_reason(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _setup_card(client, auth_headers, doc_id="schema_card.reject_m.v1")
        client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.reject_m.v1/review",
            json={"decision": "reject", "reason": "duplicate"},
            headers=auth_headers,
        )
        v = metrics_registry.counter_value(
            "rag_card_rejected_total",
            labels={"doc_type": "schema_card", "reason": "duplicate"},
        )
        assert v == 1.0

    def test_duration_histogram_observed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _setup_card(client, auth_headers, doc_id="schema_card.dur.v1")
        client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.dur.v1/review",
            json={"decision": "approve"},
            headers=auth_headers,
        )
        assert (
            metrics_registry.histogram_count(
                "rag_card_review_duration_ms",
                labels={"decision": "approve", "doc_type": "schema_card"},
            )
            == 1
        )


class TestStructuredLogs:
    def test_approve_log(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sid = _setup_card(client, auth_headers, doc_id="schema_card.log.v1")
        with caplog.at_level(
            logging.INFO, logger="fe_bot.setup.card_review.service"
        ):
            client.post(
                f"/api/v1/setup/{sid}/rag-cards-review/schema_card.log.v1/review",
                json={"decision": "approve"},
                headers=auth_headers,
            )
        msgs = [r.message for r in caplog.records]
        assert "rag_card_review_decision_made" in msgs

    def test_edit_log_has_versions(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sid = _setup_card(client, auth_headers, doc_id="schema_card.elog.v1")
        with caplog.at_level(
            logging.INFO, logger="fe_bot.setup.card_review.service"
        ):
            client.patch(
                f"/api/v1/setup/{sid}/rag-cards-review/schema_card.elog.v1",
                json={
                    "expected_version": "1.0",
                    "metadata_patch": {"title": "X"},
                },
                headers=auth_headers,
            )
        records = [r for r in caplog.records if r.message == "rag_card_edited"]
        assert records, "expected rag_card_edited log"
        rec = records[0]
        assert hasattr(rec, "previous_card_version")
        assert hasattr(rec, "new_card_version")
