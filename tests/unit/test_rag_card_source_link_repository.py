"""Unit-тесты RAGCardSourceLinkRepository (SETUP-05 / T-S05-011)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.lineage import LineageRelationType
from schemas.setup.rag_card_source_link import RAGCardSourceLinkDTO

from fe_bot.setup.rag_card_generation.source_link_repository import (
    InMemoryRAGCardSourceLinkRepository,
)

pytestmark = pytest.mark.unit


def _link(
    *,
    source_link_id: str = "lnk_001",
    doc_id: str = "analytics.x.v1",
    card_version: str = "1.0",
    source_document_id: str = "src_001",
    source_section_id: str = "sec_001",
    relation_type: LineageRelationType = LineageRelationType.GENERATED_FROM,
) -> RAGCardSourceLinkDTO:
    return RAGCardSourceLinkDTO(
        source_link_id=source_link_id,
        doc_id=doc_id,
        card_version=card_version,
        source_document_id=source_document_id,
        source_section_id=source_section_id,
        relation_type=relation_type,
        created_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


class TestIdempotency:
    def test_first_link_stored(self) -> None:
        repo = InMemoryRAGCardSourceLinkRepository()
        result = repo.link(_link())
        assert result.source_link_id == "lnk_001"

    def test_repeated_link_returns_existing(self) -> None:
        repo = InMemoryRAGCardSourceLinkRepository()
        first = repo.link(_link(source_link_id="lnk_001"))
        # Same unique key (doc_id, version, section_id, relation_type) — different id.
        second = repo.link(_link(source_link_id="lnk_002"))
        # Idempotent: returns the FIRST stored link.
        assert second.source_link_id == first.source_link_id == "lnk_001"
        assert len(repo.list_for_card("analytics.x.v1", "1.0")) == 1

    def test_different_section_creates_new(self) -> None:
        repo = InMemoryRAGCardSourceLinkRepository()
        repo.link(_link(source_link_id="lnk_001", source_section_id="sec_a"))
        repo.link(_link(source_link_id="lnk_002", source_section_id="sec_b"))
        assert len(repo.list_for_card("analytics.x.v1", "1.0")) == 2


class TestListing:
    def test_list_for_section(self) -> None:
        repo = InMemoryRAGCardSourceLinkRepository()
        repo.link(_link(source_link_id="a"))
        repo.link(
            _link(
                source_link_id="b",
                doc_id="other.v1",
                source_section_id="sec_001",
            )
        )
        result = repo.list_for_section("sec_001")
        assert {r.source_link_id for r in result} == {"a", "b"}

    def test_list_for_document(self) -> None:
        repo = InMemoryRAGCardSourceLinkRepository()
        repo.link(_link(source_link_id="a"))
        repo.link(
            _link(
                source_link_id="b",
                doc_id="other.v1",
                source_document_id="src_002",
            )
        )
        result = repo.list_for_document("src_001")
        assert len(result) == 1
        assert result[0].source_link_id == "a"


class TestSnapshot:
    def test_roundtrip(self) -> None:
        repo = InMemoryRAGCardSourceLinkRepository()
        repo.link(_link())
        snap = repo.snapshot()
        repo2 = InMemoryRAGCardSourceLinkRepository()
        repo2.restore(snap)
        assert len(repo2.list_for_card("analytics.x.v1", "1.0")) == 1
        # Idempotency сохраняется после restore — повторный link не создаёт дубль.
        repo2.link(_link(source_link_id="lnk_other"))
        assert len(repo2.list_for_card("analytics.x.v1", "1.0")) == 1
