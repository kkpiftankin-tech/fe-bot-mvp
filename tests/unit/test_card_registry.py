"""Тесты RAG Card Registry."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.rag.ontology import (
    ConfidenceLevel,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata

from fe_bot.setup.card_registry.service import (
    CardAlreadyExistsError,
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)

pytestmark = pytest.mark.unit


def _make_card_and_metadata(
    *,
    doc_id: str = "analytics_card.test.v1",
    status: CardStatus = CardStatus.GENERATED,
    doc_type: DocType = DocType.ANALYTICS_CARD,
) -> tuple[RAGCard, RAGMetadata]:
    now = datetime(2026, 6, 9, 10, 0, tzinfo=UTC)
    card = RAGCard(
        doc_id=doc_id,
        doc_type=doc_type,
        title="Test card",
        version="1.0",
        status=status,
        body_markdown="# Test\n\nbody",
        source_document_ids=["src_1"],
        created_by="generator",
        created_at=now,
        updated_at=now,
    )
    metadata = RAGMetadata(
        doc_id=doc_id,
        doc_type=doc_type,
        phase=[Phase.FEATURE_SYNTHESIS],
        domain=[Domain.NAVAL],
        task_type=[TaskType.CLASSIFICATION],
        retrieval_tags=["test"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, metadata


@pytest.fixture
def registry() -> InMemoryRAGCardRegistry:
    return InMemoryRAGCardRegistry()


class TestAdd:
    def test_add_returns_record_with_history(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, meta = _make_card_and_metadata()
        record = registry.add(
            setup_job_id="setup_1", card=card, metadata=meta, section_id="sec_1"
        )
        assert record.card.doc_id == card.doc_id
        assert record.setup_job_id == "setup_1"
        assert record.section_id == "sec_1"
        assert any("created" in h for h in record.history)
        assert registry.exists(card.doc_id)

    def test_duplicate_doc_id_raises(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, meta = _make_card_and_metadata()
        registry.add(setup_job_id="setup_1", card=card, metadata=meta)
        with pytest.raises(CardAlreadyExistsError):
            registry.add(setup_job_id="setup_1", card=card, metadata=meta)

    def test_doc_id_mismatch_raises(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, _ = _make_card_and_metadata(doc_id="a.v1")
        _, meta = _make_card_and_metadata(doc_id="b.v1")
        with pytest.raises(ValueError, match="doc_id"):
            registry.add(setup_job_id="setup_1", card=card, metadata=meta)

    def test_returned_record_is_deep_copy(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, meta = _make_card_and_metadata()
        record = registry.add(setup_job_id="setup_1", card=card, metadata=meta)
        # Мутация caller'а не должна задеть store.
        record.card.title = "Mutated"
        fetched = registry.get(card.doc_id)
        assert fetched.card.title == "Test card"


class TestGet:
    def test_get_unknown_raises(self, registry: InMemoryRAGCardRegistry) -> None:
        with pytest.raises(CardNotFoundError):
            registry.get("unknown.v1")


class TestList:
    def test_list_filters_by_setup_job(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        c1, m1 = _make_card_and_metadata(doc_id="job1.a.v1")
        c2, m2 = _make_card_and_metadata(doc_id="job1.b.v1")
        c3, m3 = _make_card_and_metadata(doc_id="job2.a.v1")
        registry.add(setup_job_id="job1", card=c1, metadata=m1)
        registry.add(setup_job_id="job1", card=c2, metadata=m2)
        registry.add(setup_job_id="job2", card=c3, metadata=m3)
        assert len(registry.list_for_job("job1")) == 2
        assert len(registry.list_for_job("job2")) == 1
        assert registry.list_for_job("nope") == []

    def test_list_filters_by_status(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        c1, m1 = _make_card_and_metadata(
            doc_id="a.v1", status=CardStatus.GENERATED
        )
        c2, m2 = _make_card_and_metadata(
            doc_id="b.v1", status=CardStatus.REVIEW_REQUIRED
        )
        c3, m3 = _make_card_and_metadata(
            doc_id="c.v1", status=CardStatus.APPROVED
        )
        registry.add(setup_job_id="j", card=c1, metadata=m1)
        registry.add(setup_job_id="j", card=c2, metadata=m2)
        registry.add(setup_job_id="j", card=c3, metadata=m3)

        all_records = registry.list_for_job("j")
        assert len(all_records) == 3

        review_only = registry.list_for_job(
            "j", status_in=frozenset({CardStatus.REVIEW_REQUIRED})
        )
        assert {r.card.doc_id for r in review_only} == {"b.v1"}


class TestUpdate:
    def test_update_card_status_appends_history(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, meta = _make_card_and_metadata()
        registry.add(setup_job_id="j", card=card, metadata=meta)
        updated_card = card.model_copy(update={"status": CardStatus.METADATA_VALIDATED})
        record = registry.update(
            card.doc_id, card=updated_card, note="validation passed"
        )
        assert record.card.status == CardStatus.METADATA_VALIDATED
        assert any("validation passed" in h for h in record.history)

    def test_update_unknown_raises(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        with pytest.raises(CardNotFoundError):
            registry.update("unknown", note="x")

    def test_update_advances_updated_at(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, meta = _make_card_and_metadata()
        before = card.updated_at
        registry.add(setup_job_id="j", card=card, metadata=meta)
        updated_card = card.model_copy(update={"status": CardStatus.METADATA_VALIDATED})
        record = registry.update(card.doc_id, card=updated_card)
        assert record.card.updated_at > before

    def test_update_doc_id_consistency_enforced(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, meta = _make_card_and_metadata()
        registry.add(setup_job_id="j", card=card, metadata=meta)
        new_meta = meta.model_copy(update={"doc_id": "other.v1"})
        with pytest.raises(ValueError, match="doc_id"):
            registry.update(card.doc_id, metadata=new_meta)


class TestDelete:
    def test_delete_unknown_raises(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        with pytest.raises(CardNotFoundError):
            registry.delete("unknown")

    def test_delete_removes_card(
        self, registry: InMemoryRAGCardRegistry
    ) -> None:
        card, meta = _make_card_and_metadata()
        registry.add(setup_job_id="j", card=card, metadata=meta)
        registry.delete(card.doc_id)
        assert not registry.exists(card.doc_id)
