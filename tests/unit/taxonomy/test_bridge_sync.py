"""Unit-тесты SectionClassTagsBridge (SETUP-12 / T-S12-042)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)
from schemas.taxonomy.state import ClassificationState, bit_offset

from fe_bot.taxonomy import (
    InMemorySectionClassTagsRepository,
    SectionClassTag,
    SectionClassTagsBridge,
    TaxonomyRegistry,
)
from fe_bot.taxonomy.bridge_sync import SectionClassTagsRepository

pytestmark = pytest.mark.unit


def _entry(
    *, level: int, parent_path: str, bit_index: int, class_slug: str
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


class TestRepository:
    def test_replace_and_list(self) -> None:
        repo = InMemorySectionClassTagsRepository()
        tags = [
            SectionClassTag(
                section_id="sec_1",
                taxonomy_version="v1.0.0",
                level=0,
                parent_path="",
                class_slug="task",
                is_primary=True,
            ),
        ]
        repo.replace_for_section("sec_1", tags)
        assert repo.list_for_section("sec_1") == tags

    def test_replace_full_overwrites(self) -> None:
        repo = InMemorySectionClassTagsRepository()
        tag1 = SectionClassTag(
            section_id="sec_1",
            taxonomy_version="v1.0.0",
            level=0,
            parent_path="",
            class_slug="task",
            is_primary=True,
        )
        tag2 = SectionClassTag(
            section_id="sec_1",
            taxonomy_version="v1.0.0",
            level=0,
            parent_path="",
            class_slug="schema",
            is_primary=True,
        )
        repo.replace_for_section("sec_1", [tag1])
        repo.replace_for_section("sec_1", [tag2])
        out = repo.list_for_section("sec_1")
        assert out == [tag2]

    def test_replace_rejects_mismatching_section(self) -> None:
        repo = InMemorySectionClassTagsRepository()
        wrong_tag = SectionClassTag(
            section_id="OTHER",
            taxonomy_version="v1.0.0",
            level=0,
            parent_path="",
            class_slug="task",
            is_primary=True,
        )
        with pytest.raises(ValueError, match="mismatches"):
            repo.replace_for_section("sec_1", [wrong_tag])

    def test_query_filters(self) -> None:
        repo = InMemorySectionClassTagsRepository()
        repo.replace_for_section(
            "sec_1",
            [
                SectionClassTag(
                    section_id="sec_1",
                    taxonomy_version="v1.0.0",
                    level=0,
                    parent_path="",
                    class_slug="task",
                    is_primary=True,
                ),
                SectionClassTag(
                    section_id="sec_1",
                    taxonomy_version="v1.0.0",
                    level=1,
                    parent_path="task",
                    class_slug="pvo",
                    is_primary=True,
                ),
            ],
        )
        repo.replace_for_section(
            "sec_2",
            [
                SectionClassTag(
                    section_id="sec_2",
                    taxonomy_version="v1.0.0",
                    level=0,
                    parent_path="",
                    class_slug="schema",
                    is_primary=True,
                )
            ],
        )
        out = repo.query(level=1)
        assert len(out) == 1
        assert out[0].section_id == "sec_1"

        out = repo.query(class_slug="task")
        assert len(out) == 1
        out = repo.query(class_slug="pvo", level=1)
        assert len(out) == 1

    def test_delete_for_section(self) -> None:
        repo = InMemorySectionClassTagsRepository()
        repo.replace_for_section(
            "sec_1",
            [
                SectionClassTag(
                    section_id="sec_1",
                    taxonomy_version="v1.0.0",
                    level=0,
                    parent_path="",
                    class_slug="task",
                    is_primary=True,
                )
            ],
        )
        repo.delete_for_section("sec_1")
        assert repo.list_for_section("sec_1") == []


class TestBridgeMaterialization:
    def test_l0_only(self) -> None:
        reg = _make_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        bridge = SectionClassTagsBridge(registry=reg)
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=1 << bit_offset(0, 0),
            primary_l0_idx=0,
            unknown_at_level=1,
        )
        tags = bridge.materialize_for_section("sec_1", state)
        assert len(tags) == 1
        assert tags[0].level == 0
        assert tags[0].parent_path == ""
        assert tags[0].class_slug == "task"
        assert tags[0].is_primary is True

    def test_l0_l1_l2_full(self) -> None:
        reg = _make_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=1,
                    parent_path="task",
                    bit_index=0,
                    class_slug="pvo",
                ),
                _entry(
                    level=2,
                    parent_path="task.pvo",
                    bit_index=0,
                    class_slug="tracking",
                ),
            ]
        )
        bridge = SectionClassTagsBridge(registry=reg)
        bitmap = (
            (1 << bit_offset(0, 0))
            | (1 << bit_offset(1, 0))
            | (1 << bit_offset(2, 0))
        )
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=bitmap,
            primary_l0_idx=0,
            primary_l1_idx=0,
        )
        tags = bridge.materialize_for_section("sec_1", state)
        assert len(tags) == 3
        levels = {t.level for t in tags}
        assert levels == {0, 1, 2}
        # parent_path для L1 = "task", для L2 = "task.pvo"
        l1_tag = next(t for t in tags if t.level == 1)
        assert l1_tag.parent_path == "task"
        l2_tag = next(t for t in tags if t.level == 2)
        assert l2_tag.parent_path == "task.pvo"

    def test_multi_class_l0(self) -> None:
        reg = _make_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=0, parent_path="", bit_index=1, class_slug="schema"
                ),
            ]
        )
        bridge = SectionClassTagsBridge(registry=reg)
        bitmap = (1 << bit_offset(0, 0)) | (1 << bit_offset(0, 1))
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=bitmap,
            primary_l0_idx=0,  # task — primary
            unknown_at_level=1,
        )
        tags = bridge.materialize_for_section("sec_1", state)
        assert len(tags) == 2
        primaries = {t.class_slug: t.is_primary for t in tags}
        assert primaries == {"task": True, "schema": False}

    def test_persists_in_repository(self) -> None:
        repo = InMemorySectionClassTagsRepository()
        reg = _make_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        bridge = SectionClassTagsBridge(registry=reg, repository=repo)
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=1 << bit_offset(0, 0),
            primary_l0_idx=0,
            unknown_at_level=1,
        )
        bridge.materialize_for_section("sec_1", state)
        # Bridge-репозиторий теперь содержит запись
        out = repo.list_for_section("sec_1")
        assert len(out) == 1

    def test_empty_state_yields_no_tags(self) -> None:
        reg = _make_registry([])
        bridge = SectionClassTagsBridge(registry=reg)
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=0,
        )
        tags = bridge.materialize_for_section("sec_x", state)
        assert tags == []

    def test_delete_section(self) -> None:
        repo = InMemorySectionClassTagsRepository()
        reg = _make_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        bridge = SectionClassTagsBridge(registry=reg, repository=repo)
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=1 << bit_offset(0, 0),
            primary_l0_idx=0,
            unknown_at_level=1,
        )
        bridge.materialize_for_section("sec_x", state)
        bridge.delete_for_section("sec_x")
        assert repo.list_for_section("sec_x") == []


class TestGlobalQuery:
    def test_query_finds_section_by_l1_class_across_parents(self) -> None:
        """Глобальный запрос: «все секции с классом ПВО на уровне 1»,
        независимо от того, что primary_l0 был.
        """
        reg = _make_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(level=0, parent_path="", bit_index=2, class_slug="analytics"),
                _entry(
                    level=1,
                    parent_path="task",
                    bit_index=0,
                    class_slug="pvo",
                ),
                _entry(
                    level=1,
                    parent_path="analytics",
                    bit_index=0,
                    class_slug="pvo",  # one и тот же slug под другим parent
                ),
            ]
        )
        bridge = SectionClassTagsBridge(registry=reg)

        # Section A — task.pvo
        state_a = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=(1 << bit_offset(0, 0)) | (1 << bit_offset(1, 0)),
            primary_l0_idx=0,
            primary_l1_idx=0,
            unknown_at_level=2,
        )
        bridge.materialize_for_section("sec_A", state_a)

        # Section B — analytics.pvo
        state_b = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=(1 << bit_offset(0, 2)) | (1 << bit_offset(1, 0)),
            primary_l0_idx=2,
            primary_l1_idx=0,
            unknown_at_level=2,
        )
        bridge.materialize_for_section("sec_B", state_b)

        # Section C — task.something-else (для отрицательного контроля,
        # но мы не делаем — пропустим)

        repo: SectionClassTagsRepository = bridge.repository
        results = repo.query(level=1, class_slug="pvo")
        section_ids = {t.section_id for t in results}
        assert section_ids == {"sec_A", "sec_B"}
