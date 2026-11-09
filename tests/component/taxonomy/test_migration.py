"""Component-тесты v0_to_v1 миграции (SETUP-12 / T-S12-080, T-S12-081)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from schemas.setup.parsed_section import (
    ParsedSection,
    SectionType,
)
from schemas.taxonomy.state import bit_offset

from fe_bot.taxonomy import (
    TaxonomyRegistry,
    load_seed_taxonomy,
)
from fe_bot.taxonomy.migration import (
    BackfillReport,
    backfill_classification_state,
    backfill_front_matter,
    backfill_section,
    migrate_cards,
    migrate_sections,
)

pytestmark = pytest.mark.component


def _seed_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "seed"
        / "taxonomy"
        / "v1_0_0.yaml"
    )


def _registry() -> TaxonomyRegistry:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(load_seed_taxonomy(_seed_path()))
    return reg


def _section(
    *,
    section_type: SectionType,
    confidence: float = 0.8,
    section_id: str = "sec_1",
    classification_state: object | None = None,
) -> ParsedSection:
    return ParsedSection(
        section_id=section_id,
        parse_job_id="pj_1",
        source_document_id="src_1",
        title="Test",
        heading_path=["Test"],
        section_type=section_type,
        raw_text="x" * 20,
        normalized_text="x" * 20,
        confidence=confidence,
        created_at=datetime.now(tz=UTC),
        classification_state=classification_state,
    )


# ----------------------------------------------------------------------
# backfill_classification_state
# ----------------------------------------------------------------------


class TestBackfillState:
    def test_task_maps_to_bit_0(self) -> None:
        reg = _registry()
        state = backfill_classification_state(
            _section(section_type=SectionType.TASK), registry=reg
        )
        assert state.primary_l0_idx == 0
        assert state.classification_bitmap == 1 << bit_offset(0, 0)
        assert state.unknown_at_level == 1
        assert state.confidence_per_level[0] == pytest.approx(0.8)
        assert state.confidence_per_bit == {"0:0": 0.8}
        assert state.classification_method == "seeded_migration"
        assert state.taxonomy_version_id == "v1.0.0"

    @pytest.mark.parametrize(
        "section_type,expected_bit,expected_slug",
        [
            (SectionType.TASK, 0, "task"),
            (SectionType.SCHEMA, 1, "schema"),
            (SectionType.ANALYTICS, 2, "analytics"),
            (SectionType.GLOSSARY, 3, "glossary"),
            (SectionType.VALIDATION, 4, "validation_rule"),
            (SectionType.VALIDATION_RULE, 4, "validation_rule"),
            (SectionType.QUESTION_TEMPLATE, 5, "question_template"),
            (SectionType.DOMAIN_PROFILE, 6, "domain_profile"),
        ],
    )
    def test_all_legacy_mappings(
        self,
        section_type: SectionType,
        expected_bit: int,
        expected_slug: str,
    ) -> None:
        reg = _registry()
        state = backfill_classification_state(
            _section(section_type=section_type), registry=reg
        )
        assert state.primary_l0_idx == expected_bit
        assert state.unknown_at_level == 1

    def test_other_maps_to_unknown(self) -> None:
        reg = _registry()
        state = backfill_classification_state(
            _section(section_type=SectionType.OTHER, confidence=0.5),
            registry=reg,
        )
        assert state.unknown_at_level == 0
        assert state.primary_l0_idx is None
        assert state.classification_bitmap == 0
        assert state.classification_method == "seeded_migration_unknown"

    def test_unknown_maps_to_unknown(self) -> None:
        reg = _registry()
        state = backfill_classification_state(
            _section(section_type=SectionType.UNKNOWN), registry=reg
        )
        assert state.unknown_at_level == 0
        assert state.primary_l0_idx is None


class TestBackfillSection:
    def test_idempotency(self) -> None:
        reg = _registry()
        # First migration
        section = _section(section_type=SectionType.TASK)
        migrated = backfill_section(section, registry=reg)
        assert migrated.classification_state is not None
        # Repeat: should not change
        migrated2 = backfill_section(migrated, registry=reg)
        assert migrated2 is migrated

    def test_returns_copy(self) -> None:
        reg = _registry()
        section = _section(section_type=SectionType.TASK)
        migrated = backfill_section(section, registry=reg)
        # Original section_type stays the same
        assert section.classification_state is None
        assert migrated.classification_state is not None
        assert migrated.section_type == SectionType.TASK


# ----------------------------------------------------------------------
# backfill_front_matter
# ----------------------------------------------------------------------


class TestBackfillFrontMatter:
    def test_adds_taxonomy_fields(self) -> None:
        reg = _registry()
        section = _section(section_type=SectionType.SCHEMA)
        fm: dict[str, Any] = {"existing_field": "stays"}
        updated = backfill_front_matter(section, fm, registry=reg)
        assert updated["existing_field"] == "stays"
        assert updated["taxonomy_version_id"] == "v1.0.0"
        assert updated["primary_l0"] == "schema"
        assert updated["taxonomy_path"] == ["schema"]
        assert updated["taxonomy_node_id"] == "schema"
        assert updated["unknown_at_level"] == 1

    def test_idempotency(self) -> None:
        reg = _registry()
        section = _section(section_type=SectionType.TASK)
        fm = backfill_front_matter(section, {}, registry=reg)
        # Re-run: no changes
        fm2 = backfill_front_matter(section, fm, registry=reg)
        assert fm == fm2

    def test_unknown_section_minimal_fm(self) -> None:
        reg = _registry()
        section = _section(section_type=SectionType.OTHER)
        fm = backfill_front_matter(section, {}, registry=reg)
        # OTHER → unknown_at_level=0 → minimal block (no path/node_id)
        assert fm["taxonomy_version_id"] == "v1.0.0"
        assert fm["classification_bitmap"] == 0
        assert fm["unknown_at_level"] == 0
        assert "taxonomy_path" not in fm


# ----------------------------------------------------------------------
# migrate_sections (batch)
# ----------------------------------------------------------------------


class _FakeSectionRepo:
    def __init__(self, sections: list[ParsedSection]) -> None:
        self._sections = {s.section_id: s for s in sections}
        self.upserts: list[ParsedSection] = []

    def list_all(self) -> list[ParsedSection]:
        return list(self._sections.values())

    def upsert(self, section: ParsedSection) -> None:
        self._sections[section.section_id] = section
        self.upserts.append(section)


class TestMigrateSections:
    def test_dry_run_does_not_persist(self) -> None:
        reg = _registry()
        sections = [
            _section(section_id="a", section_type=SectionType.TASK),
            _section(section_id="b", section_type=SectionType.SCHEMA),
            _section(section_id="c", section_type=SectionType.OTHER),
        ]
        repo = _FakeSectionRepo(sections)
        report = migrate_sections(repo, registry=reg, dry_run=True)
        assert report.total == 3
        assert report.migrated == 3
        assert report.skipped == 0
        assert report.unknown == 1  # OTHER
        assert report.success
        # dry_run → upserts не должны были произойти
        assert repo.upserts == []

    def test_apply_persists(self) -> None:
        reg = _registry()
        sections = [
            _section(section_id="a", section_type=SectionType.TASK),
            _section(section_id="b", section_type=SectionType.SCHEMA),
        ]
        repo = _FakeSectionRepo(sections)
        report = migrate_sections(repo, registry=reg, dry_run=False)
        assert report.migrated == 2
        assert len(repo.upserts) == 2
        # Все upsert'ы имеют classification_state
        for s in repo.upserts:
            assert s.classification_state is not None

    def test_skips_already_migrated(self) -> None:
        reg = _registry()
        # Один уже мигрированный + один новый
        migrated_section = backfill_section(
            _section(section_id="a", section_type=SectionType.TASK),
            registry=reg,
        )
        sections = [
            migrated_section,
            _section(section_id="b", section_type=SectionType.SCHEMA),
        ]
        repo = _FakeSectionRepo(sections)
        report = migrate_sections(repo, registry=reg, dry_run=False)
        assert report.skipped == 1
        assert report.migrated == 1


# ----------------------------------------------------------------------
# migrate_cards (batch)
# ----------------------------------------------------------------------


class _FakeCard:
    def __init__(
        self,
        *,
        doc_id: str,
        source_section_ids: list[str],
        front_matter: dict[str, Any] | None = None,
    ) -> None:
        self.doc_id = doc_id
        self.source_section_ids = source_section_ids
        self.front_matter = front_matter or {}


class TestMigrateCards:
    def test_dry_run_does_not_mutate(self) -> None:
        reg = _registry()
        section = _section(section_id="sec_x", section_type=SectionType.SCHEMA)
        card = _FakeCard(
            doc_id="schema.x.v1",
            source_section_ids=["sec_x"],
            front_matter={"existing": "x"},
        )
        report = migrate_cards(
            [card],
            sections_by_id={"sec_x": section},
            registry=reg,
            dry_run=True,
        )
        assert report.migrated == 1
        # front_matter не должен быть тронут в dry-run
        assert "taxonomy_version_id" not in card.front_matter

    def test_apply_mutates_front_matter(self) -> None:
        reg = _registry()
        section = _section(section_id="sec_x", section_type=SectionType.SCHEMA)
        card = _FakeCard(
            doc_id="schema.x.v1",
            source_section_ids=["sec_x"],
            front_matter={"existing": "x"},
        )
        report = migrate_cards(
            [card],
            sections_by_id={"sec_x": section},
            registry=reg,
            dry_run=False,
        )
        assert report.migrated == 1
        assert card.front_matter["existing"] == "x"
        assert card.front_matter["taxonomy_version_id"] == "v1.0.0"
        assert card.front_matter["primary_l0"] == "schema"
        assert card.front_matter["taxonomy_path"] == ["schema"]

    def test_idempotency(self) -> None:
        reg = _registry()
        section = _section(section_id="sec_x", section_type=SectionType.TASK)
        card = _FakeCard(
            doc_id="task.x.v1",
            source_section_ids=["sec_x"],
            front_matter={
                "taxonomy_version_id": "v0.9.0",  # уже мигрирован
            },
        )
        report = migrate_cards(
            [card],
            sections_by_id={"sec_x": section},
            registry=reg,
            dry_run=False,
        )
        assert report.skipped == 1
        assert card.front_matter["taxonomy_version_id"] == "v0.9.0"

    def test_missing_source_section_counts_as_unknown(self) -> None:
        reg = _registry()
        card = _FakeCard(
            doc_id="orphan.v1",
            source_section_ids=["nonexistent"],
        )
        report = migrate_cards(
            [card], sections_by_id={}, registry=reg, dry_run=False
        )
        assert report.unknown == 1
        assert report.migrated == 0

    def test_no_source_sections(self) -> None:
        reg = _registry()
        card = _FakeCard(doc_id="x.v1", source_section_ids=[])
        report = migrate_cards(
            [card], sections_by_id={}, registry=reg, dry_run=False
        )
        assert report.unknown == 1


# ----------------------------------------------------------------------
# BackfillReport
# ----------------------------------------------------------------------


class TestBackfillReport:
    def test_success_when_no_errors(self) -> None:
        r = BackfillReport(total=5, migrated=5)
        assert r.success is True

    def test_fail_when_has_errors(self) -> None:
        r = BackfillReport(total=5, migrated=4, errors=["x"])
        assert r.success is False
