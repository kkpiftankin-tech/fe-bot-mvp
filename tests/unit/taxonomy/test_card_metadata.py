"""Unit-тесты card_metadata helpers (SETUP-12 / T-S12-051, T-S12-052)."""

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
from schemas.taxonomy.state import ClassificationState, bit_offset

from fe_bot.taxonomy import (
    TaxonomyRegistry,
    build_taxonomy_front_matter,
    build_taxonomy_section_dict,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    level: int,
    parent_path: str,
    bit_index: int,
    class_slug: str,
    doc_type_hint: str | None = None,
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


def _make_section(
    *,
    state: ClassificationState | None = None,
) -> ParsedSection:
    return ParsedSection(
        section_id="sec_1",
        parse_job_id="pj",
        source_document_id="src",
        title="Test",
        heading_path=["Test"],
        section_type=SectionType.TASK,
        raw_text="x" * 20,
        normalized_text="x" * 20,
        confidence=0.5,
        created_at=datetime.now(tz=UTC),
        classification_state=state,
    )


# ----------------------------------------------------------------------
# build_taxonomy_front_matter
# ----------------------------------------------------------------------


class TestBuildFrontMatter:
    def test_none_state_returns_empty(self) -> None:
        reg = _make_registry([])
        fm = build_taxonomy_front_matter(_make_section(), registry=reg)
        assert fm == {}

    def test_unknown_at_l0_returns_minimal(self) -> None:
        reg = _make_registry([])
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=0,
        )
        fm = build_taxonomy_front_matter(
            _make_section(state=state), registry=reg
        )
        assert fm["taxonomy_version_id"] == "v1.0.0"
        assert fm["classification_bitmap"] == 0
        assert fm["unknown_at_level"] == 0
        assert "taxonomy_path" not in fm
        assert "taxonomy_node_id" not in fm

    def test_l0_only_path(self) -> None:
        reg = _make_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=1 << bit_offset(0, 0),
            primary_l0_idx=0,
            unknown_at_level=1,
        )
        fm = build_taxonomy_front_matter(
            _make_section(state=state), registry=reg
        )
        assert fm["taxonomy_path"] == ["task"]
        assert fm["taxonomy_node_id"] == "task"
        assert fm["primary_l0"] == "task"
        assert "primary_l1" not in fm
        assert fm["unknown_at_level"] == 1
        assert fm["classification_bitmap"] == 1
        assert fm["taxonomy_version_id"] == "v1.0.0"

    def test_full_l0_l1_l2_path(self) -> None:
        reg = _make_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=1, parent_path="task", bit_index=0, class_slug="pvo"
                ),
                _entry(
                    level=2,
                    parent_path="task.pvo",
                    bit_index=0,
                    class_slug="tracking",
                ),
            ]
        )
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=(
                (1 << bit_offset(0, 0))
                | (1 << bit_offset(1, 0))
                | (1 << bit_offset(2, 0))
            ),
            primary_l0_idx=0,
            primary_l1_idx=0,
        )
        fm = build_taxonomy_front_matter(
            _make_section(state=state), registry=reg
        )
        assert fm["taxonomy_path"] == ["task", "pvo", "tracking"]
        assert fm["primary_l0"] == "task"
        assert fm["primary_l1"] == "pvo"
        # unknown_at_level=None → ключа в front_matter нет
        assert "unknown_at_level" not in fm


# ----------------------------------------------------------------------
# build_taxonomy_section_dict
# ----------------------------------------------------------------------


class TestBuildSectionDict:
    def test_none_state_returns_empty(self) -> None:
        reg = _make_registry([])
        out = build_taxonomy_section_dict(_make_section(), registry=reg)
        assert out == {}

    def test_l0_l1(self) -> None:
        reg = _make_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=1, parent_path="task", bit_index=0, class_slug="pvo"
                ),
            ]
        )
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=(1 << bit_offset(0, 0)) | (1 << bit_offset(1, 0)),
            primary_l0_idx=0,
            primary_l1_idx=0,
            unknown_at_level=2,
        )
        out = build_taxonomy_section_dict(
            _make_section(state=state), registry=reg
        )
        assert out["taxonomy_version"] == "v1.0.0"
        assert out["taxonomy_path"] == ["task", "pvo"]
        assert out["primary_l0"] == "task"
        assert out["primary_l1"] == "pvo"
        assert out["unknown_at_level"] == 2

    def test_unknown_at_l0_returns_empty(self) -> None:
        reg = _make_registry([])
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=0,
        )
        out = build_taxonomy_section_dict(
            _make_section(state=state), registry=reg
        )
        assert out == {}
