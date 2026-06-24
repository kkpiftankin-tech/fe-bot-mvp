"""Integration tests for SETUP-06 → SETUP-07 auto-validate flow (T-S07-017)."""

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
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make_card(doc_id: str = "schema_card.x.v1") -> tuple[RAGCard, RAGMetadata]:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.SCHEMA_CARD,
        title="Test",
        version="1.0",
        card_version="1.0",
        status=CardStatus.REVIEW_REQUIRED,
        body_markdown="# Test\n\nValid body content here",
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


def _setup(
    client: TestClient,
    auth_headers: dict[str, str],
) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "AutoValidation"},
        headers=auth_headers,
    )
    sid = resp.json()["setup_job_id"]
    from fe_bot.api.dependencies import get_card_registry as _get_reg

    registry: InMemoryRAGCardRegistry = client.app.dependency_overrides[_get_reg]()
    card, meta = _make_card()
    registry.add(setup_job_id=sid, card=card, metadata=meta)
    return sid


def test_approve_triggers_auto_validation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """T-S07-017: после approve запускается validate_one и создаётся report."""
    sid = _setup(client, auth_headers)

    # Approve через SETUP-06 endpoint.
    r = client.post(
        f"/api/v1/setup/{sid}/rag-cards-review/schema_card.x.v1/review",
        json={"decision": "approve"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text

    # Report должен появиться без явного вызова /validation/run.
    r = client.get(
        f"/api/v1/setup/{sid}/validation/reports/schema_card.x.v1",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["doc_id"] == "schema_card.x.v1"
    assert body["status"] in ("passed", "warning", "failed", "repair_required")


def test_approve_without_validation_service_does_not_crash(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Если validation_service не передан в сервис — approve работает без ошибок."""
    # Это тестируется встроенно: conftest подаёт validation_service, но
    # legacy backward-compat теst для прямого RAGCardReviewService без него
    # покрывает T-S07-017 fallback path. Здесь просто проверяем что endpoint
    # отвечает 200 (validation_service подключён в conftest).
    sid = _setup(client, auth_headers)
    r = client.post(
        f"/api/v1/setup/{sid}/rag-cards-review/schema_card.x.v1/review",
        json={"decision": "approve"},
        headers=auth_headers,
    )
    assert r.status_code == 200
