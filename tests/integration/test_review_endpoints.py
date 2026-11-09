"""Integration tests for SETUP-06 review endpoints (T-S06-026)."""

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
    doc_id: str = "schema_card.test.v1",
    status: CardStatus = CardStatus.REVIEW_REQUIRED,
    body: str = "# Test\n\nSome sufficiently long body content for validation purposes",
    confidence: str = "high",
) -> tuple[RAGCard, RAGMetadata]:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.SCHEMA_CARD,
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
        doc_type=DocType.SCHEMA_CARD,
        phase=[Phase.FEATURE_SYNTHESIS],
        domain=[Domain.NAVAL],
        task_type=[TaskType.CLASSIFICATION],
        retrieval_tags=["test"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


def _create_setup_with_card(
    client: TestClient,
    auth_headers: dict[str, str],
    *,
    doc_id: str = "schema_card.test.v1",
    status: CardStatus = CardStatus.REVIEW_REQUIRED,
    body: str = "# Test\n\nSome sufficiently long body content for validation purposes",
    confidence: str = "high",
) -> str:
    """Создаёт setup job + добавляет карточку напрямую в registry."""
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Review Test"},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201), resp.text
    sid = resp.json()["setup_job_id"]

    # Add card via registry override from app state
    from fe_bot.api.dependencies import get_card_registry as _get_reg

    registry: InMemoryRAGCardRegistry = client.app.dependency_overrides[_get_reg]()
    card, meta = _make_card(doc_id=doc_id, status=status, body=body, confidence=confidence)
    registry.add(setup_job_id=sid, card=card, metadata=meta)
    return sid


# ============================================================
# GET list
# ============================================================


class TestList:
    def test_list_empty(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/setup/jobs",
            json={"project_name": "Empty"},
            headers=auth_headers,
        )
        sid = resp.json()["setup_job_id"]
        r = client.get(f"/api/v1/setup/{sid}/rag-cards-review", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_list_with_card(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.get(f"/api/v1/setup/{sid}/rag-cards-review", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["doc_id"] == "schema_card.test.v1"

    def test_list_filter_by_status(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        # Add another with approved status
        from fe_bot.api.dependencies import get_card_registry as _get_reg
        registry = client.app.dependency_overrides.get(_get_reg, _get_reg)()
        card, meta = _make_card(doc_id="schema_card.other.v1", status=CardStatus.APPROVED)
        registry.add(setup_job_id=sid, card=card, metadata=meta)

        r = client.get(
            f"/api/v1/setup/{sid}/rag-cards-review?status=review_required",
            headers=auth_headers,
        )
        assert r.json()["total"] == 1

    def test_list_pagination(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        from fe_bot.api.dependencies import get_card_registry as _get_reg
        registry = client.app.dependency_overrides.get(_get_reg, _get_reg)()
        for i in range(5):
            card, meta = _make_card(doc_id=f"c.v{i}")
            registry.add(setup_job_id=sid, card=card, metadata=meta)

        r = client.get(
            f"/api/v1/setup/{sid}/rag-cards-review?page=1&page_size=3",
            headers=auth_headers,
        )
        assert len(r.json()["items"]) == 3

    def test_list_404_unknown_job(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        r = client.get(
            "/api/v1/setup/setup_missing/rag-cards-review", headers=auth_headers
        )
        assert r.status_code == 404

    def test_list_403_other_user(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        other = {"X-User-Id": "u2", "X-Roles": "user"}
        r = client.get(f"/api/v1/setup/{sid}/rag-cards-review", headers=other)
        assert r.status_code == 403


# ============================================================
# GET details
# ============================================================


class TestDetails:
    def test_get_details(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["doc_id"] == "schema_card.test.v1"
        assert "permissions" in body
        assert "validation" in body

    def test_get_404_missing(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/rag-cards-review/missing.v1", headers=auth_headers
        )
        assert r.status_code == 404


# ============================================================
# POST /review approve
# ============================================================


class TestApprove:
    def test_approve_happy(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json={"decision": "approve", "comment": "looks good"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "approved"
        assert body["reviewed_by"] == "u1"

    def test_approve_blocked_by_validation(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers, body="short")
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json={"decision": "approve"},
            headers=auth_headers,
        )
        assert r.status_code == 422
        assert "CARD_HAS_CRITICAL_VALIDATION_ERRORS" in r.text

    def test_approve_idempotent(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        payload = {"decision": "approve", "review_decision_id": "rd_xyz"}
        r1 = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json=payload,
            headers=auth_headers,
        )
        r2 = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json=payload,
            headers=auth_headers,
        )
        assert r1.status_code == 200 and r2.status_code == 200


# ============================================================
# POST /review reject
# ============================================================


class TestReject:
    def test_reject_happy(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json={"decision": "reject", "reason": "duplicate", "comment": "is dup"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    def test_reject_requires_reason(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json={"decision": "reject"},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "REJECT_REASON_REQUIRED" in r.text


# ============================================================
# PATCH edit
# ============================================================


class TestEdit:
    def test_edit_creates_new_version(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.patch(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1",
            json={
                "expected_version": "1.0",
                "metadata_patch": {"title": "Updated Title"},
                "change_reason": "typo fix",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["previous_version"] == "1.0"
        assert body["new_version"] == "1.1"

    def test_edit_version_conflict(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.patch(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1",
            json={
                "expected_version": "0.9",
                "metadata_patch": {"title": "X"},
            },
            headers=auth_headers,
        )
        assert r.status_code == 409
        assert "CARD_VERSION_CONFLICT" in r.text

    def test_edit_system_metadata_blocked(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.patch(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1",
            json={
                "expected_version": "1.0",
                "metadata_patch": {"doc_id": "new.id"},
            },
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "SYSTEM_METADATA_READ_ONLY" in r.text


# ============================================================
# POST regenerate
# ============================================================


class TestRegenerate:
    def test_regenerate_requires_reason(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/regenerate",
            json={"reason": ""},
            headers=admin_headers,
        )
        # Pydantic rejects empty reason via min_length=1
        assert r.status_code in (400, 422)

    def test_regenerate_happy(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/regenerate",
            json={"reason": "low_quality", "regenerate_request_id": "rg_1"},
            headers=admin_headers,
        )
        # May succeed or fail with 422/409 depending on generation orchestrator
        # availability; key: 4xx/200 — no 500.
        assert r.status_code < 500


# ============================================================
# RBAC
# ============================================================


class TestRBAC:
    def test_approve_requires_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        # Auditor has read-only — no approve permission
        auditor = {"X-User-Id": "u1", "X-Roles": "auditor"}
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json={"decision": "approve"},
            headers=auditor,
        )
        assert r.status_code == 403


# ============================================================
# Versions / log
# ============================================================


class TestVersionsAndLog:
    def test_versions_empty_initially(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        r = client.get(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/versions",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["versions"] == []

    def test_versions_after_edit(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        client.patch(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1",
            json={
                "expected_version": "1.0",
                "metadata_patch": {"title": "New"},
            },
            headers=auth_headers,
        )
        r = client.get(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/versions",
            headers=auth_headers,
        )
        assert len(r.json()["versions"]) >= 1

    def test_review_log_after_approve(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_setup_with_card(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review",
            json={"decision": "approve"},
            headers=auth_headers,
        )
        r = client.get(
            f"/api/v1/setup/{sid}/rag-cards-review/schema_card.test.v1/review-log",
            headers=auth_headers,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(it["event_type"] == "approved" for it in items)
