"""Integration: POST /api/v1/setup/{id}/retrieval-tests (T-S01-037)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx
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
from fe_bot.vector_index.client import (
    InMemoryVectorIndexClient,
    VectorPoint,
    collection_for_doc_type,
)

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime(2026, 6, 10, 10, 0, tzinfo=UTC)


def _seed_vector_index(client: InMemoryVectorIndexClient) -> None:
    """Кладём 3 точки с разными векторами."""
    collection = collection_for_doc_type("analytics_card")
    client.upsert(
        collection=collection,
        point=VectorPoint(
            chunk_id="a1#summary#0",
            doc_id="a1",
            doc_type="analytics_card",
            chunk_type="summary",
            vector=[1.0] + [0.0] * 767,
            payload={"doc_id": "a1"},
        ),
    )
    client.upsert(
        collection=collection,
        point=VectorPoint(
            chunk_id="a2#summary#0",
            doc_id="a2",
            doc_type="analytics_card",
            chunk_type="summary",
            vector=[0.0, 1.0] + [0.0] * 766,
            payload={"doc_id": "a2"},
        ),
    )


def _add_card(
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
        json={"project_name": "Eval KB"},
        headers=headers,
    )
    return create.json()["setup_job_id"]


class TestRetrievalTestsHappyPath:
    @respx.mock
    def test_passing_eval_returns_passed_true(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json={"embedding": [1.0] + [0.0] * 767}
        )
        from fe_bot.api.dependencies import get_vector_index_client

        index = app_with_clean_state.dependency_overrides[get_vector_index_client]()
        _seed_vector_index(index)

        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/retrieval-tests",
            json={
                "golden_queries": [
                    {"query": "find a1", "expected_doc_ids": ["a1"]},
                ],
                "top_k": 5,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["passed"] is True
        assert body["queries_total"] == 1
        assert body["mean_recall_at_k"] == 1.0
        assert body["per_query"][0]["retrieved_doc_ids"][0] == "a1"

    @respx.mock
    def test_failing_eval_returns_passed_false(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json={"embedding": [1.0] + [0.0] * 767}
        )
        from fe_bot.api.dependencies import get_vector_index_client

        index = app_with_clean_state.dependency_overrides[get_vector_index_client]()
        _seed_vector_index(index)

        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/retrieval-tests",
            json={
                "golden_queries": [
                    # Ожидаем doc-id, которого нет в индексе.
                    {"query": "find missing", "expected_doc_ids": ["missing"]},
                ],
                "top_k": 3,
                "threshold_recall_at_5": 0.85,
            },
            headers=auth_headers,
        )
        body = resp.json()
        assert body["passed"] is False
        assert body["mean_recall_at_k"] == 0.0

    @respx.mock
    def test_custom_threshold_override(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json={"embedding": [1.0] + [0.0] * 767}
        )
        from fe_bot.api.dependencies import get_vector_index_client

        index = app_with_clean_state.dependency_overrides[get_vector_index_client]()
        _seed_vector_index(index)

        sid = _create_job(client, auth_headers)
        # threshold_recall_at_5=0.1 — очень низкий, любой ненулевой recall пройдёт.
        resp = client.post(
            f"/api/v1/setup/{sid}/retrieval-tests",
            json={
                "golden_queries": [
                    {
                        "query": "find a1",
                        "expected_doc_ids": ["a1", "a2", "missing"],
                    },
                ],
                "top_k": 1,
                "threshold_recall_at_5": 0.1,
            },
            headers=auth_headers,
        )
        body = resp.json()
        # recall = 1/3 = 0.33 > 0.1 → passed
        assert body["passed"] is True


class TestRetrievalTestsErrors:
    def test_unknown_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post(
            "/api/v1/setup/unknown/retrieval-tests",
            json={"golden_queries": [{"query": "x", "expected_doc_ids": ["a"]}]},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_empty_golden_queries_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/retrieval-tests",
            json={"golden_queries": []},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_auditor_lacks_setup_run_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/retrieval-tests",
            json={"golden_queries": [{"query": "x", "expected_doc_ids": ["a"]}]},
            headers={"X-User-Id": "auditor", "X-Roles": "auditor"},
        )
        assert resp.status_code == 403


class TestUseHttpx:
    def test_smoke(self) -> None:
        assert httpx.codes.OK == 200
