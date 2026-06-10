"""Тесты Chunking Service (T-S01-029)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.rag.chunk import ChunkType
from schemas.rag.ontology import (
    ConfidenceLevel,
    DataSource,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata

from fe_bot.setup.chunking.service import (
    CHUNK_CHAR_BUDGET,
    SUMMARY_CHAR_BUDGET,
    ChunkingService,
)

pytestmark = pytest.mark.unit


def _now() -> datetime:
    return datetime(2026, 6, 10, 10, 0, tzinfo=UTC)


def _make_pair(
    *,
    doc_id: str = "analytics_card.sensor.v1",
    body: str | None = None,
    source_section_id: str | None = "sec_1",
) -> tuple[RAGCard, RAGMetadata]:
    body = body or "# Sensor analytics\n\nbody body body."
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        title="Sensor analytics T",
        version="1.0",
        status=CardStatus.APPROVED,
        body_markdown=body,
        source_document_ids=["src_1"],
        source_section_ids=[source_section_id] if source_section_id else [],
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
        data_source=[DataSource.RADAR],
        agent_targets=["FeatureSynthesisAgent"],
        retrieval_tags=["sensor", "uptime"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


class TestBasicChunking:
    def test_each_card_produces_3_chunks(self) -> None:
        card, meta = _make_pair()
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        assert len(chunks) == 3
        assert {c.chunk_type for c in chunks} == {
            ChunkType.SUMMARY,
            ChunkType.DEFINITION,
            ChunkType.METADATA_SUMMARY,
        }

    def test_chunk_id_is_deterministic(self) -> None:
        """INV-ID-003: повторный chunking даёт идентичные chunk_id."""
        card, meta = _make_pair()
        svc = ChunkingService()
        first = svc.chunk_card(card=card, metadata=meta)
        second = svc.chunk_card(card=card, metadata=meta)
        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]

    def test_chunk_id_format(self) -> None:
        card, meta = _make_pair(doc_id="x.y.v1")
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        ids = {c.chunk_id for c in chunks}
        assert "x.y.v1#summary#0" in ids
        assert "x.y.v1#definition#0" in ids
        assert "x.y.v1#metadata_summary#0" in ids

    def test_doc_id_propagated(self) -> None:
        card, meta = _make_pair(doc_id="my.card.v1")
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        assert all(c.doc_id == "my.card.v1" for c in chunks)

    def test_mismatched_doc_ids_raise(self) -> None:
        card, meta = _make_pair(doc_id="a.v1")
        meta2 = meta.model_copy(update={"doc_id": "b.v1"})
        with pytest.raises(ValueError, match="doc_id"):
            ChunkingService().chunk_card(card=card, metadata=meta2)


class TestEmbeddingText:
    def test_embedding_text_is_lowercased(self) -> None:
        card, meta = _make_pair(body="UPPERCASE body content")
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        for c in chunks:
            # Должно быть lowercased + ASCII-нормализованным.
            assert c.embedding_text == c.embedding_text.lower()

    def test_embedding_text_collapses_whitespace(self) -> None:
        card, meta = _make_pair(body="text\n\nwith   multiple\twhitespace")
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        definition = next(c for c in chunks if c.chunk_type == ChunkType.DEFINITION)
        assert "  " not in definition.embedding_text
        assert "\t" not in definition.embedding_text
        assert "\n" not in definition.embedding_text

    def test_embedding_text_truncated_at_budget(self) -> None:
        long_body = "x" * (CHUNK_CHAR_BUDGET * 2)
        card, meta = _make_pair(body=long_body)
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        for c in chunks:
            assert len(c.embedding_text) <= CHUNK_CHAR_BUDGET


class TestBudget:
    def test_definition_truncated_at_budget(self) -> None:
        long_body = "x" * (CHUNK_CHAR_BUDGET * 2)
        card, meta = _make_pair(body=long_body)
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        definition = next(c for c in chunks if c.chunk_type == ChunkType.DEFINITION)
        # +1 для "…" символа
        assert len(definition.chunk_text) <= CHUNK_CHAR_BUDGET + 1
        assert definition.chunk_text.endswith("…")

    def test_summary_truncated_at_summary_budget(self) -> None:
        long_body = "x" * (SUMMARY_CHAR_BUDGET * 3)
        card, meta = _make_pair(body=long_body)
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        summary = next(c for c in chunks if c.chunk_type == ChunkType.SUMMARY)
        assert len(summary.chunk_text) <= SUMMARY_CHAR_BUDGET + 1
        assert summary.chunk_text.endswith("…")

    def test_short_body_not_truncated(self) -> None:
        card, meta = _make_pair(body="short body")
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        summary = next(c for c in chunks if c.chunk_type == ChunkType.SUMMARY)
        assert summary.chunk_text == "short body"
        assert not summary.chunk_text.endswith("…")


class TestMetadataSummary:
    def test_metadata_summary_includes_phases_tags_domain(self) -> None:
        card, meta = _make_pair()
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        ms = next(c for c in chunks if c.chunk_type == ChunkType.METADATA_SUMMARY)
        assert "feature_synthesis" in ms.embedding_text
        assert "naval" in ms.embedding_text
        assert "uptime" in ms.embedding_text
        assert "featuresynthesisagent" in ms.embedding_text  # lowercased


class TestPriorities:
    def test_summary_has_highest_priority(self) -> None:
        card, meta = _make_pair()
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        summary = next(c for c in chunks if c.chunk_type == ChunkType.SUMMARY)
        definition = next(c for c in chunks if c.chunk_type == ChunkType.DEFINITION)
        ms = next(c for c in chunks if c.chunk_type == ChunkType.METADATA_SUMMARY)
        assert summary.priority > definition.priority > ms.priority


class TestSection:
    def test_section_id_propagated(self) -> None:
        card, meta = _make_pair(source_section_id="my_sec")
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        assert all(c.source_section_id == "my_sec" for c in chunks)

    def test_no_section_id_propagates_none(self) -> None:
        card, meta = _make_pair(source_section_id=None)
        chunks = ChunkingService().chunk_card(card=card, metadata=meta)
        assert all(c.source_section_id is None for c in chunks)


class TestChunkMany:
    def test_chunk_many_concatenates(self) -> None:
        pairs = [_make_pair(doc_id=f"x.{i}.v1") for i in range(3)]
        chunks = ChunkingService().chunk_many(pairs)
        assert len(chunks) == 9  # 3 cards × 3 chunks
        assert len({c.doc_id for c in chunks}) == 3
