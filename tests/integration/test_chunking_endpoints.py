"""Integration tests for SETUP-08 chunking endpoints (T-S08-013)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

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


def _make_card(
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


def _setup_with_card(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    doc_id: str = "schema_card.test.v1",
    status: CardStatus = CardStatus.METADATA_VALIDATED,
) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Chunking"},
        headers=auth_headers,
    )
    sid = resp.json()["setup_job_id"]
    from fe_bot.api.dependencies import get_card_registry as _get_reg

    registry: InMemoryRAGCardRegistry = client.app.dependency_overrides[_get_reg]()
    card, meta = _make_card(doc_id=doc_id, status=status)
    registry.add(setup_job_id=sid, card=card, metadata=meta)
    return sid


class TestRun:
    def test_run_chunking(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_cards"] == 1
        assert body["chunks_created"] == 3

    def test_run_requires_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        auditor = {"X-User-Id": "u1", "X-Roles": "auditor"}
        r = client.post(
            f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auditor
        )
        assert r.status_code == 403

    def test_run_404_unknown_job(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        r = client.post(
            "/api/v1/setup/setup_missing/chunking/run",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestManifest:
    def test_manifest_404_when_no_run(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/chunking/manifest", headers=auth_headers
        )
        assert r.status_code == 404

    def test_manifest_after_run(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
        )
        r = client.get(
            f"/api/v1/setup/{sid}/chunking/manifest", headers=auth_headers
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total_chunks"] == 3
        assert "summary" in body["by_type"]


class TestPreview:
    def test_preview_returns_3_chunks(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/chunking/preview/schema_card.test.v1",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["chunks"]) == 3

    def test_preview_does_not_persist(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        client.get(
            f"/api/v1/setup/{sid}/chunking/preview/schema_card.test.v1",
            headers=auth_headers,
        )
        # Manifest should still not exist
        r = client.get(
            f"/api/v1/setup/{sid}/chunking/manifest", headers=auth_headers
        )
        assert r.status_code == 404

    def test_preview_cross_job_isolation(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid1 = _setup_with_card(client, auth_headers, doc_id="a.v1")
        sid2 = _setup_with_card(client, auth_headers, doc_id="b.v1")
        # Try to preview a.v1 from sid2 — should 404
        r = client.get(
            f"/api/v1/setup/{sid2}/chunking/preview/a.v1",
            headers=auth_headers,
        )
        assert r.status_code == 404


class TestRefresh:
    def test_refresh_persists_manifest(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/chunking/refresh/schema_card.test.v1",
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        # Manifest should now exist
        m = client.get(
            f"/api/v1/setup/{sid}/chunking/manifest", headers=auth_headers
        )
        assert m.status_code == 200


class TestRBAC:
    def test_auditor_can_read_manifest(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/chunking/run", json={}, headers=auth_headers
        )
        auditor = {"X-User-Id": "u1", "X-Roles": "auditor"}
        r = client.get(
            f"/api/v1/setup/{sid}/chunking/manifest", headers=auditor
        )
        assert r.status_code == 200

    def test_auditor_cannot_refresh(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _setup_with_card(client, auth_headers)
        auditor = {"X-User-Id": "u1", "X-Roles": "auditor"}
        r = client.post(
            f"/api/v1/setup/{sid}/chunking/refresh/schema_card.test.v1",
            headers=auditor,
        )
        assert r.status_code == 403
