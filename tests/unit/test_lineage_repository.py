"""Unit-тесты LineageRepository (T-S03-008)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.lineage import (
    LineageRelationType,
    LineageTargetType,
    SourceLineageRelation,
)

from fe_bot.setup.source_registry.lineage import InMemoryLineageRepository

pytestmark = pytest.mark.unit


def _rel(
    *,
    lin_id: str = "lin_001",
    source_id: str = "src_001",
    target_type: LineageTargetType = LineageTargetType.RAG_CARD,
    target_id: str = "card_v1",
    relation_type: LineageRelationType = LineageRelationType.GENERATED_FROM,
    event_id: str = "evt_001",
) -> SourceLineageRelation:
    return SourceLineageRelation(
        lineage_id=lin_id,
        source_document_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relation_type=relation_type,
        created_by_service="test-svc",
        event_id=event_id,
        created_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )


class TestLinkAndDedup:
    def test_link_stores(self) -> None:
        repo = InMemoryLineageRepository()
        stored = repo.link(_rel())
        assert stored.lineage_id == "lin_001"

    def test_idempotent_by_event_id(self) -> None:
        repo = InMemoryLineageRepository()
        first = repo.link(_rel())
        # Тот же event_id, но другой lineage_id → должна вернуться first.
        second = repo.link(_rel(lin_id="lin_OTHER", event_id="evt_001"))
        assert second.lineage_id == first.lineage_id

    def test_idempotent_by_unique_key(self) -> None:
        """Тот же (source, target_type, target_id, relation), другой event_id.

        Это защита от дубликата с разными event_id (например, retry с новым
        event_id, но того же логического link). Возвращается уже сохранённая
        relation.
        """
        repo = InMemoryLineageRepository()
        first = repo.link(_rel(event_id="evt_A"))
        second = repo.link(
            _rel(lin_id="lin_OTHER", event_id="evt_B")
        )
        assert second.lineage_id == first.lineage_id
        assert len(repo.list_for_source("src_001")) == 1


class TestListAndReverseLookup:
    def test_list_for_source(self) -> None:
        repo = InMemoryLineageRepository()
        repo.link(_rel(lin_id="l1", event_id="e1", target_id="card_a"))
        repo.link(_rel(lin_id="l2", event_id="e2", target_id="card_b"))
        items = repo.list_for_source("src_001")
        assert {i.target_id for i in items} == {"card_a", "card_b"}

    def test_list_for_source_filter_by_target_type(self) -> None:
        repo = InMemoryLineageRepository()
        repo.link(_rel(lin_id="l1", event_id="e1", target_type=LineageTargetType.RAG_CARD))
        repo.link(
            _rel(
                lin_id="l2",
                event_id="e2",
                target_type=LineageTargetType.PARSED_SECTION,
                target_id="sec_001",
                relation_type=LineageRelationType.PARSED_FROM,
            )
        )
        cards = repo.list_for_source(
            "src_001", target_type=LineageTargetType.RAG_CARD
        )
        assert len(cards) == 1
        assert cards[0].lineage_id == "l1"

    def test_list_by_target_reverse_lookup(self) -> None:
        """Какие source documents породили этот RAG card."""
        repo = InMemoryLineageRepository()
        repo.link(_rel(lin_id="l1", source_id="src_A", event_id="e1", target_id="card_x"))
        repo.link(_rel(lin_id="l2", source_id="src_B", event_id="e2", target_id="card_x"))
        repo.link(_rel(lin_id="l3", source_id="src_C", event_id="e3", target_id="card_y"))
        sources_of_x = repo.list_by_target(LineageTargetType.RAG_CARD, "card_x")
        assert {r.source_document_id for r in sources_of_x} == {"src_A", "src_B"}


class TestCounters:
    def test_counters_aggregate_by_target_type(self) -> None:
        repo = InMemoryLineageRepository()
        # 2 cards, 3 sections, 1 KB version.
        repo.link(_rel(lin_id="l1", event_id="e1", target_id="card_a"))
        repo.link(_rel(lin_id="l2", event_id="e2", target_id="card_b"))
        for i, sec in enumerate(["sec_1", "sec_2", "sec_3"]):
            repo.link(
                _rel(
                    lin_id=f"l_sec_{i}",
                    event_id=f"e_sec_{i}",
                    target_type=LineageTargetType.PARSED_SECTION,
                    target_id=sec,
                    relation_type=LineageRelationType.PARSED_FROM,
                )
            )
        repo.link(
            _rel(
                lin_id="l_kb",
                event_id="e_kb",
                target_type=LineageTargetType.KNOWLEDGE_BASE_VERSION,
                target_id="kb_v1",
                relation_type=LineageRelationType.INCLUDED_IN,
            )
        )
        counters = repo.counters("src_001")
        assert counters.rag_cards_count == 2
        assert counters.parsed_sections_count == 3
        assert counters.knowledge_base_versions_count == 1
        assert counters.chunks_count == 0

    def test_counters_empty_for_unknown_source(self) -> None:
        repo = InMemoryLineageRepository()
        c = repo.counters("nope")
        assert c.rag_cards_count == 0


class TestGetByEventId:
    def test_get_by_event_id(self) -> None:
        repo = InMemoryLineageRepository()
        repo.link(_rel())
        assert repo.get_by_event_id("evt_001") is not None
        assert repo.get_by_event_id("nope") is None
