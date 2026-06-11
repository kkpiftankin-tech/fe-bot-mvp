"""Unit-тесты Lineage DTO (T-S03-004)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.lineage import (
    LineageCounters,
    LineageRelationType,
    LineageTargetType,
    SourceLineageDTO,
    SourceLineageRelation,
)

pytestmark = pytest.mark.unit


def _make_relation(**overrides: object) -> SourceLineageRelation:
    defaults: dict[str, object] = {
        "lineage_id": "lin_001",
        "source_document_id": "src_001",
        "target_type": LineageTargetType.RAG_CARD,
        "target_id": "card_schema_v1",
        "relation_type": LineageRelationType.GENERATED_FROM,
        "created_by_service": "rag-card-generator",
        "event_id": "evt_link_001",
        "created_at": datetime(2026, 6, 10, 10, 5, tzinfo=UTC),
        "metadata": {},
    }
    defaults.update(overrides)
    return SourceLineageRelation(**defaults)  # type: ignore[arg-type]


class TestSourceLineageRelation:
    def test_valid_minimal(self) -> None:
        rel = _make_relation()
        assert rel.target_type == LineageTargetType.RAG_CARD
        assert rel.relation_type == LineageRelationType.GENERATED_FROM

    def test_frozen_after_creation(self) -> None:
        rel = _make_relation()
        with pytest.raises(ValidationError):
            rel.target_id = "new_id"  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            _make_relation(extra="x")

    def test_target_id_max_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_relation(target_id="x" * 256)

    def test_event_id_required(self) -> None:
        with pytest.raises(ValidationError):
            _make_relation(event_id="")


class TestLineageTargetType:
    def test_all_target_types(self) -> None:
        targets = {t.value for t in LineageTargetType}
        assert targets == {
            "parsed_section",
            "rag_card",
            "chunk",
            "embedding",
            "processing_report",
            "knowledge_base_version",
        }


class TestLineageRelationType:
    def test_all_relation_types(self) -> None:
        rels = {r.value for r in LineageRelationType}
        assert rels == {
            "parsed_from",
            "generated_from",
            "derived_from",
            "included_in",
            "referenced_by",
        }


class TestLineageCounters:
    def test_defaults_are_zero(self) -> None:
        c = LineageCounters()
        assert c.parsed_sections_count == 0
        assert c.rag_cards_count == 0
        assert c.knowledge_base_versions_count == 0

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LineageCounters(rag_cards_count=-1)


class TestSourceLineageDTO:
    def test_empty_lineage(self) -> None:
        dto = SourceLineageDTO(source_document_id="src_001")
        assert dto.relations == []
        assert dto.counters.rag_cards_count == 0

    def test_with_relations_and_counters(self) -> None:
        dto = SourceLineageDTO(
            source_document_id="src_001",
            relations=[
                _make_relation(),
                _make_relation(
                    lineage_id="lin_002",
                    target_type=LineageTargetType.PARSED_SECTION,
                    target_id="sec_001",
                    relation_type=LineageRelationType.PARSED_FROM,
                    created_by_service="parser",
                    event_id="evt_002",
                ),
            ],
            counters=LineageCounters(
                parsed_sections_count=1,
                rag_cards_count=1,
            ),
        )
        assert len(dto.relations) == 2
        assert dto.counters.parsed_sections_count == 1

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            SourceLineageDTO(
                source_document_id="src_001",
                extra="x",  # type: ignore[call-arg]
            )

    def test_all_5_target_relation_combinations(self) -> None:
        """Покрытие комбинаций target × relation."""
        combos = [
            (LineageTargetType.PARSED_SECTION, LineageRelationType.PARSED_FROM),
            (LineageTargetType.RAG_CARD, LineageRelationType.GENERATED_FROM),
            (LineageTargetType.CHUNK, LineageRelationType.DERIVED_FROM),
            (LineageTargetType.KNOWLEDGE_BASE_VERSION, LineageRelationType.INCLUDED_IN),
            (LineageTargetType.PROCESSING_REPORT, LineageRelationType.REFERENCED_BY),
        ]
        for target, rel_type in combos:
            r = _make_relation(target_type=target, relation_type=rel_type)
            assert r.target_type == target
            assert r.relation_type == rel_type
