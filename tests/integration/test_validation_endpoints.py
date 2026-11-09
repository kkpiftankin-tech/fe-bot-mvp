"""Integration tests for SETUP-07 validation endpoints (T-S07-013)."""

from __future__ import annotations

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

from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make_card(
    doc_id: str = "analytics_card.test.v1",
    status: CardStatus = CardStatus.APPROVED,
    body: str = "# Test\n\nValid body content for validation",
) -> tuple[RAGCard, RAGMetadata]:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        title="Test",
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
        retrieval_tags=["test"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


def _setup_with_card(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    doc_id: str = "analytics_card.test.v1",
    status: CardStatus = CardStatus.APPROVED,
) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Validation"},
        headers=auth_headers,
    )
    sid = resp.json()["setup_job_id"]
    from fe_bot.api.dependencies import get_card_registry as _get_reg

    registry: InMemoryRAGCardRegistry = client.app.dependency_overrides[_get_reg]()
    card, meta = _make_card(doc_id=doc_id, status=status)
    registry.add(setup_job_id=sid, card=card, metadata=meta)
    return sid


class TestRun:
    def test_run_validation_happy(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed"
        assert body["total"] >= 1
        assert body["triggered_by"] == "u1"

    def test_run_requires_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        auditor = {"X-User-Id": "u1", "X-Roles": "auditor"}
        r = client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auditor
        )
        assert r.status_code == 403

    def test_run_404_unknown_job(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        r = client.post(
            "/api/v1/setup/setup_missing/validation/run",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestReports:
    def test_list_reports_empty_initially(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/validation/reports", headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_reports_after_run(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        r = client.get(
            f"/api/v1/setup/{sid}/validation/reports", headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_single_report(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        r = client.get(
            f"/api/v1/setup/{sid}/validation/reports/analytics_card.test.v1",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["doc_id"] == "analytics_card.test.v1"
        assert body["setup_job_id"] == sid

    def test_get_report_for_missing_card(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/validation/reports/missing.v1",
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_get_report_cross_job_isolation(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid1 = _setup_with_card(client, auth_headers, doc_id="a.v1")
        sid2 = _setup_with_card(client, auth_headers, doc_id="b.v1")
        client.post(
            f"/api/v1/setup/{sid1}/validation/run",
            json={},
            headers=auth_headers,
        )
        r = client.get(
            f"/api/v1/setup/{sid2}/validation/reports/a.v1",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestRefresh:
    def test_refresh_card(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/validation/reports/analytics_card.test.v1/refresh",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["doc_id"] == "analytics_card.test.v1"

    def test_refresh_missing_card(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/validation/reports/missing.v1/refresh",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestSummary:
    def test_summary_empty(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/validation/summary", headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_summary_after_run(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        r = client.get(
            f"/api/v1/setup/{sid}/validation/summary", headers=auth_headers
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        assert body["last_run_id"] is not None


class TestRBAC:
    def test_auditor_can_read(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/validation/run", json={}, headers=auth_headers
        )
        auditor = {"X-User-Id": "u1", "X-Roles": "auditor"}
        r = client.get(
            f"/api/v1/setup/{sid}/validation/reports", headers=auditor
        )
        assert r.status_code == 200

    def test_auditor_cannot_refresh(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        auditor = {"X-User-Id": "u1", "X-Roles": "auditor"}
        r = client.post(
            f"/api/v1/setup/{sid}/validation/reports/analytics_card.test.v1/refresh",
            json={},
            headers=auditor,
        )
        assert r.status_code == 403
