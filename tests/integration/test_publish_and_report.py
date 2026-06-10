"""Integration: POST /publish + GET /report (T-S01-039)."""

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
    return datetime(2026, 6, 10, 10, 0, tzinfo=UTC)


def _admin_headers() -> dict[str, str]:
    return {"X-User-Id": "admin1", "X-Roles": "admin"}


def _auditor_headers() -> dict[str, str]:
    return {"X-User-Id": "auditor", "X-Roles": "auditor"}


def _add_approved_card(
    registry: InMemoryRAGCardRegistry, setup_job_id: str, doc_id: str
) -> None:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        title=f"Card {doc_id}",
        version="1.0",
        status=CardStatus.APPROVED,
        body_markdown="body",
        source_document_ids=["src"],
        created_by="g",
        created_at=_now(),
        updated_at=_now(),
    )
    meta = RAGMetadata(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        phase=[Phase.FEATURE_SYNTHESIS],
        domain=[Domain.NAVAL],
        task_type=[TaskType.CLASSIFICATION],
        retrieval_tags=["t"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    registry.add(setup_job_id=setup_job_id, card=card, metadata=meta)


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    create = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Publish KB"},
        headers=headers,
    )
    return create.json()["setup_job_id"]


class TestPublishHappyPath:
    def test_publish_with_passed_eval(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_card_registry

        sid = _create_job(client, auth_headers)
        registry = app_with_clean_state.dependency_overrides[get_card_registry]()
        _add_approved_card(registry, sid, "a1.v1")

        # Минимальный валидный eval_report (passed=True).
        eval_payload = {
            "setup_job_id": sid,
            "queries_total": 1,
            "queries_errored": 0,
            "top_k": 5,
            "threshold_recall_at_5": 0.85,
            "mean_recall_at_k": 0.9,
            "mean_precision_at_k": 0.5,
            "mean_reciprocal_rank": 1.0,
            "no_context_rate": 0.0,
            "passed": True,
            "per_query": [],
            "message": None,
        }
        resp = client.post(
            f"/api/v1/setup/{sid}/publish",
            json={"eval_report": eval_payload, "comment": "looks good"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["status"] == "active"
        assert body["is_active"] is True
        assert body["published_by"] == "admin1"
        assert body["knowledge_base_version"].startswith("kb_")
        assert body["rag_card_count"] == 1


class TestPublishErrors:
    def test_publish_without_approved_cards_409(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/publish",
            json={},
            headers=_admin_headers(),
        )
        assert resp.status_code == 409
        assert "No approved cards" in resp.json()["detail"]

    def test_publish_with_failed_eval_409(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_card_registry

        sid = _create_job(client, auth_headers)
        registry = app_with_clean_state.dependency_overrides[get_card_registry]()
        _add_approved_card(registry, sid, "a1.v1")

        eval_payload = {
            "setup_job_id": sid,
            "queries_total": 1,
            "queries_errored": 0,
            "top_k": 5,
            "threshold_recall_at_5": 0.85,
            "mean_recall_at_k": 0.1,
            "mean_precision_at_k": 0.0,
            "mean_reciprocal_rank": 0.0,
            "no_context_rate": 1.0,
            "passed": False,
            "per_query": [],
            "message": None,
        }
        resp = client.post(
            f"/api/v1/setup/{sid}/publish",
            json={"eval_report": eval_payload},
            headers=_admin_headers(),
        )
        assert resp.status_code == 409
        assert "gate not passed" in resp.json()["detail"]

    def test_publish_requires_publish_permission(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_card_registry

        sid = _create_job(client, auth_headers)
        registry = app_with_clean_state.dependency_overrides[get_card_registry]()
        _add_approved_card(registry, sid, "a1.v1")
        resp = client.post(
            f"/api/v1/setup/{sid}/publish",
            json={},
            headers=auth_headers,  # role=user, без kb.publish
        )
        assert resp.status_code == 403

    def test_publish_unknown_job_404(
        self, client: TestClient
    ) -> None:
        resp = client.post(
            "/api/v1/setup/unknown/publish",
            json={},
            headers=_admin_headers(),
        )
        assert resp.status_code == 404


class TestReport:
    def test_report_empty_job(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        # Auditor has KB_REPORT_READ permission
        resp = client.get(
            f"/api/v1/setup/{sid}/report", headers=_auditor_headers()
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_job_id"] == sid
        assert body["status"] == "draft"
        assert body["documents_count"] == 0
        assert body["cards_count"] == 0
        assert body["knowledge_base_version"] is None
        assert body["eval_passed"] is None

    def test_report_after_publish(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_card_registry

        sid = _create_job(client, auth_headers)
        registry = app_with_clean_state.dependency_overrides[get_card_registry]()
        _add_approved_card(registry, sid, "a1.v1")

        eval_payload = {
            "setup_job_id": sid,
            "queries_total": 1,
            "queries_errored": 0,
            "top_k": 5,
            "threshold_recall_at_5": 0.85,
            "mean_recall_at_k": 0.9,
            "mean_precision_at_k": 0.5,
            "mean_reciprocal_rank": 1.0,
            "no_context_rate": 0.0,
            "passed": True,
            "per_query": [],
            "message": None,
        }
        client.post(
            f"/api/v1/setup/{sid}/publish",
            json={"eval_report": eval_payload},
            headers=_admin_headers(),
        )

        report = client.get(
            f"/api/v1/setup/{sid}/report", headers=_auditor_headers()
        ).json()
        assert report["cards_count"] == 1
        # После publish карточка переведена в PUBLISHED — статус не "approved",
        # но cards_approved считает APPROVED+CHUNKED+EMBEDDED+INDEXED+PUBLISHED.
        assert report["cards_approved"] == 1
        assert report["knowledge_base_version"] is not None
        assert report["knowledge_base_status"] == "active"
        assert report["knowledge_base_is_active"] is True
        assert report["eval_passed"] is True

    def test_report_unknown_job_404(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/setup/unknown/report", headers=_auditor_headers()
        )
        assert resp.status_code == 404
