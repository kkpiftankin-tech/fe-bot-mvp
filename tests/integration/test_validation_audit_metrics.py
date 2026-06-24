"""Integration tests for SETUP-07 audit + metrics + structured logs (T-S07-018..020)."""

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
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _setup_card(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    doc_id: str = "schema_card.audit.v1",
) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "AuditVal"},
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
        status=CardStatus.APPROVED,
        body_markdown="# Test\n\nValid body content",
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
    def test_run_writes_validation_audit_actions(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _setup_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        assert r.status_code == 200
        actions = {e.action for e in audit_log.list_for_job(sid)}
        assert AuditAction.VALIDATION_RUN_TRIGGERED in actions
        assert AuditAction.VALIDATION_REPORT_CREATED in actions

    def test_refresh_writes_audit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _setup_card(client, auth_headers, doc_id="schema_card.refresh.v1")
        client.post(
            f"/api/v1/setup/{sid}/validation/reports/schema_card.refresh.v1/refresh",
            json={},
            headers=auth_headers,
        )
        actions = [e.action for e in audit_log.list_for_job(sid)]
        assert AuditAction.VALIDATION_REPORT_CREATED in actions


class TestMetrics:
    def test_runs_total_counter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _setup_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        v = metrics_registry.counter_value(
            "validation_runs_total", labels={"outcome": "completed"}
        )
        assert v >= 1.0

    def test_reports_counter_by_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _setup_card(client, auth_headers, doc_id="schema_card.metric.v1")
        client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        # Хотя бы один report зарегистрирован (любой status).
        text = metrics_registry.render_prometheus()
        assert "validation_reports_total" in text

    def test_card_duration_histogram(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _setup_card(client, auth_headers, doc_id="schema_card.dur.v1")
        client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        count = metrics_registry.histogram_count("validation_card_duration_ms")
        assert count >= 1


class TestStructuredLogs:
    def test_run_completed_log(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sid = _setup_card(client, auth_headers, doc_id="schema_card.log.v1")
        with caplog.at_level(
            logging.INFO, logger="fe_bot.setup.metadata_validation.service"
        ):
            client.post(
                f"/api/v1/setup/{sid}/validation/run",
                json={},
                headers=auth_headers,
            )
        records = [r for r in caplog.records if r.message == "validation_run_completed"]
        assert records, "expected validation_run_completed log"
        rec = records[0]
        for attr in ("validation_run_id", "total", "duration_ms", "outcome"):
            assert hasattr(rec, attr), f"missing {attr} on log record"
