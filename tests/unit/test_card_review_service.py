"""Тесты RAG Card Review Service (T-S01-025)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.rag.ontology import ConfidenceLevel, DocType, Domain, Phase, TaskType
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata

from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.card_review.service import (
    InvalidEditPayloadError,
    InvalidReviewStateError,
    RAGCardReviewService,
    _bump_version,
    _new_doc_id,
)

pytestmark = pytest.mark.unit


def _make_pair(
    *,
    doc_id: str = "analytics_card.test.v1",
    status: CardStatus = CardStatus.REVIEW_REQUIRED,
) -> tuple[RAGCard, RAGMetadata]:
    now = datetime(2026, 6, 9, 10, 0, tzinfo=UTC)
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        title="Test card",
        version="1.0",
        status=status,
        body_markdown="# Test\n\nold body",
        source_document_ids=["src_1"],
        created_by="generator",
        created_at=now,
        updated_at=now,
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


@pytest.fixture
def registry_with_card() -> tuple[InMemoryRAGCardRegistry, RAGCardReviewService]:
    registry = InMemoryRAGCardRegistry()
    card, meta = _make_pair()
    registry.add(setup_job_id="j1", card=card, metadata=meta)
    svc = RAGCardReviewService(registry)
    return registry, svc


class TestApprove:
    def test_approve_from_review_required(
        self,
        registry_with_card: tuple[InMemoryRAGCardRegistry, RAGCardReviewService],
    ) -> None:
        registry, svc = registry_with_card
        result = svc.approve(
            doc_id="analytics_card.test.v1",
            reviewer_id="alice",
            comment="ok",
        )
        assert result.card.status == CardStatus.APPROVED
        assert result.card.reviewed_by == "alice"
        rec = registry.get("analytics_card.test.v1")
        assert rec.card.status == CardStatus.APPROVED
        assert any("approve by alice" in h for h in rec.history)


class TestReject:
    def test_reject_from_review_required(
        self,
        registry_with_card: tuple[InMemoryRAGCardRegistry, RAGCardReviewService],
    ) -> None:
        registry, svc = registry_with_card
        result = svc.reject(
            doc_id="analytics_card.test.v1",
            reviewer_id="alice",
            comment="bad metadata",
        )
        assert result.card.status == CardStatus.DEPRECATED
        rec = registry.get("analytics_card.test.v1")
        assert rec.card.status == CardStatus.DEPRECATED
        assert any("reject by alice" in h for h in rec.history)


class TestEdit:
    def test_edit_creates_new_version_old_deprecated(
        self,
        registry_with_card: tuple[InMemoryRAGCardRegistry, RAGCardReviewService],
    ) -> None:
        registry, svc = registry_with_card
        new_record = svc.edit(
            doc_id="analytics_card.test.v1",
            reviewer_id="alice",
            updated_body_markdown="# Test\n\nnew body",
            comment="fixed typo",
        )
        # Новая карточка имеет новый doc_id (v1.1), APPROVED, новый body.
        assert new_record.card.doc_id == "analytics_card.test.v1.1"
        assert new_record.card.version == "1.1"
        assert new_record.card.status == CardStatus.APPROVED
        assert "new body" in new_record.card.body_markdown
        assert new_record.card.front_matter.get("supersedes") == "analytics_card.test.v1"

        # Старая → DEPRECATED.
        old = registry.get("analytics_card.test.v1")
        assert old.card.status == CardStatus.DEPRECATED

    def test_edit_title_only(
        self,
        registry_with_card: tuple[InMemoryRAGCardRegistry, RAGCardReviewService],
    ) -> None:
        _, svc = registry_with_card
        new_record = svc.edit(
            doc_id="analytics_card.test.v1",
            reviewer_id="alice",
            updated_title="Renamed",
        )
        assert new_record.card.title == "Renamed"
        assert "old body" in new_record.card.body_markdown

    def test_edit_without_payload_raises(
        self,
        registry_with_card: tuple[InMemoryRAGCardRegistry, RAGCardReviewService],
    ) -> None:
        _, svc = registry_with_card
        with pytest.raises(InvalidEditPayloadError):
            svc.edit(doc_id="analytics_card.test.v1", reviewer_id="alice")


class TestRegenerate:
    def test_regenerate_returns_to_draft(
        self,
        registry_with_card: tuple[InMemoryRAGCardRegistry, RAGCardReviewService],
    ) -> None:
        registry, svc = registry_with_card
        result = svc.regenerate(
            doc_id="analytics_card.test.v1",
            reviewer_id="alice",
            comment="needs rewording",
        )
        assert result.card.status == CardStatus.DRAFT
        rec = registry.get("analytics_card.test.v1")
        assert rec.card.status == CardStatus.DRAFT


class TestErrors:
    def test_unknown_card_raises(self) -> None:
        registry = InMemoryRAGCardRegistry()
        svc = RAGCardReviewService(registry)
        with pytest.raises(CardNotFoundError):
            svc.approve(doc_id="nope", reviewer_id="alice")

    def test_approve_on_already_approved_raises(self) -> None:
        registry = InMemoryRAGCardRegistry()
        card, meta = _make_pair(status=CardStatus.APPROVED)
        registry.add(setup_job_id="j", card=card, metadata=meta)
        svc = RAGCardReviewService(registry)
        with pytest.raises(InvalidReviewStateError):
            svc.approve(doc_id=card.doc_id, reviewer_id="alice")


class TestVersionHelpers:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("1", "2"),
            ("1.0", "1.1"),
            ("2.5", "2.6"),
            ("1.2.3", "1.2.4"),
        ],
    )
    def test_bump_version(self, version: str, expected: str) -> None:
        assert _bump_version(version) == expected

    def test_new_doc_id_replaces_v_suffix(self) -> None:
        assert (
            _new_doc_id("schema_card.tracks.v1", "1.1")
            == "schema_card.tracks.v1.1"
        )

    def test_new_doc_id_without_v_suffix(self) -> None:
        # Если doc_id не следует соглашению `…vN`, делаем append.
        assert _new_doc_id("custom_id", "1.1") == "custom_id.1.1"
