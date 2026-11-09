"""Unit-тесты TaxonomyDocTypeDetector (SETUP-12 / T-S12-050)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.parsed_section import (
    ParsedSection,
    SectionType,
)
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)
from schemas.taxonomy.state import (
    ClassificationState,
    bit_offset,
)

from fe_bot.setup.rag_card_generation.doc_type_detector import DocTypeDetector
from fe_bot.taxonomy import TaxonomyDocTypeDetector, TaxonomyRegistry

pytestmark = pytest.mark.unit


def _entry(
    *,
    bit_index: int,
    class_slug: str,
    doc_type_hint: str | None,
    level: int = 0,
    parent_path: str = "",
) -> TaxonomyBitRegistryEntry:
    return TaxonomyBitRegistryEntry(
        version_id="v1.0.0",
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=f"Класс {class_slug}",
        description=f"Описание {class_slug}.",
        created_at=datetime.now(tz=UTC),
        doc_type_hint=doc_type_hint,
    )


def _make_section(
    *,
    section_type: SectionType = SectionType.TASK,
    classification_state: ClassificationState | None = None,
    title: str = "Test",
) -> ParsedSection:
    return ParsedSection(
        section_id="sec_1",
        parse_job_id="pj",
        source_document_id="src",
        title=title,
        heading_path=[title],
        section_type=section_type,
        raw_text="x" * 20,
        normalized_text="x" * 20,
        confidence=0.5,
        created_at=datetime.now(tz=UTC),
        classification_state=classification_state,
    )


def _make_registry(entries: list[TaxonomyBitRegistryEntry]) -> TaxonomyRegistry:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(
        TaxonomyVersion(
            version_id="v1.0.0",
            created_at=datetime.now(tz=UTC),
            is_active=True,
            entries=entries,
        )
    )
    return reg


class TestTaxonomyHint:
    def test_reads_doc_type_hint_from_registry(self) -> None:
        reg = _make_registry(
            [
                _entry(
                    bit_index=1,
                    class_slug="schema",
                    doc_type_hint="schema_card",
                )
            ]
        )
        detector = TaxonomyDocTypeDetector(
            registry=reg, legacy=DocTypeDetector()
        )
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=1 << bit_offset(0, 1),
            primary_l0_idx=1,
            unknown_at_level=1,
        )
        section = _make_section(classification_state=state)
        decision = detector.detect(section)
        assert decision.doc_type == "schema_card"
        assert decision.confidence == 0.95
        assert decision.reason == "taxonomy_hint"

    def test_falls_back_when_no_hint(self) -> None:
        reg = _make_registry(
            [
                _entry(
                    bit_index=9,
                    class_slug="auto_created",
                    doc_type_hint=None,  # auto-created, без hint
                )
            ]
        )
        detector = TaxonomyDocTypeDetector(
            registry=reg, legacy=DocTypeDetector()
        )
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=1 << bit_offset(0, 9),
            primary_l0_idx=9,
            unknown_at_level=1,
        )
        # legacy: section_type=TASK → task_card.
        section = _make_section(
            section_type=SectionType.TASK,
            classification_state=state,
        )
        decision = detector.detect(section)
        # Fallback на legacy.
        assert decision.doc_type == "task_card"
        assert decision.reason == "direct_mapping"

    def test_fallback_when_no_classification_state(self) -> None:
        reg = _make_registry(
            [
                _entry(
                    bit_index=0,
                    class_slug="task",
                    doc_type_hint="task_card",
                )
            ]
        )
        detector = TaxonomyDocTypeDetector(
            registry=reg, legacy=DocTypeDetector()
        )
        section = _make_section(
            section_type=SectionType.SCHEMA,
            classification_state=None,  # rule-based mode
        )
        decision = detector.detect(section)
        # Legacy: section_type=SCHEMA → schema_card.
        assert decision.doc_type == "schema_card"
        assert decision.reason == "direct_mapping"


class TestRegistryLookupFailure:
    def test_missing_bit_falls_back(self) -> None:
        # primary_l0_idx указывает на bit, которого нет в registry.
        # Defensive: fallback на legacy.
        reg = _make_registry([])  # пустой
        detector = TaxonomyDocTypeDetector(
            registry=reg, legacy=DocTypeDetector()
        )
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=0,
        )
        section = _make_section(
            section_type=SectionType.TASK,
            classification_state=state,
        )
        decision = detector.detect(section)
        # Legacy mapping для TASK
        assert decision.doc_type == "task_card"
