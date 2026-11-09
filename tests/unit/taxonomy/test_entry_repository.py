"""Unit-тесты InMemoryTaxonomyEntryRepository (SETUP-12 / T-S12-011)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyBitStatus,
)

from fe_bot.taxonomy.entry_repository import (
    DuplicateRegistryEntryError,
    InMemoryTaxonomyEntryRepository,
    RegistryEntryNotFoundError,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    level: int = 0,
    parent_path: str = "",
    bit_index: int = 0,
    class_slug: str = "task",
    version_id: str = "v1.0.0",
    **overrides: object,
) -> TaxonomyBitRegistryEntry:
    defaults: dict[str, object] = {
        "version_id": version_id,
        "level": level,
        "parent_path": parent_path,
        "bit_index": bit_index,
        "class_slug": class_slug,
        "display_name_ru": f"Класс {class_slug}",
        "description": "Описание класса для теста.",
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    return TaxonomyBitRegistryEntry(**defaults)  # type: ignore[arg-type]


class TestCreateAndGet:
    def test_create_and_get(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry())
        out = repo.get(
            version_id="v1.0.0", level=0, parent_path="", bit_index=0
        )
        assert out.class_slug == "task"

    def test_duplicate_bit_rejected(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(bit_index=0, class_slug="task"))
        with pytest.raises(DuplicateRegistryEntryError):
            repo.create(_entry(bit_index=0, class_slug="other"))

    def test_duplicate_slug_rejected(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(bit_index=0, class_slug="task"))
        with pytest.raises(DuplicateRegistryEntryError):
            repo.create(_entry(bit_index=1, class_slug="task"))

    def test_get_missing(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        with pytest.raises(RegistryEntryNotFoundError):
            repo.get(
                version_id="v1.0.0", level=0, parent_path="", bit_index=5
            )


class TestListUnder:
    def test_empty(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        assert (
            repo.list_under(version_id="v1.0.0", level=0, parent_path="")
            == []
        )

    def test_sorted_by_bit_index(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(bit_index=3, class_slug="three"))
        repo.create(_entry(bit_index=0, class_slug="zero"))
        repo.create(_entry(bit_index=1, class_slug="one"))
        out = repo.list_under(version_id="v1.0.0", level=0, parent_path="")
        assert [e.bit_index for e in out] == [0, 1, 3]

    def test_filtered_by_parent_path(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(level=1, parent_path="task", bit_index=0, class_slug="pvo"))
        repo.create(
            _entry(level=1, parent_path="schema", bit_index=0, class_slug="etl")
        )
        out_task = repo.list_under(version_id="v1.0.0", level=1, parent_path="task")
        assert len(out_task) == 1
        assert out_task[0].class_slug == "pvo"

    def test_only_active_default(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(bit_index=0, class_slug="active"))
        repo.create(
            _entry(
                bit_index=1,
                class_slug="dead",
                status=TaxonomyBitStatus.DEPRECATED_MERGED,
                merged_into_slug="active",
            )
        )
        out = repo.list_under(version_id="v1.0.0", level=0, parent_path="")
        assert [e.class_slug for e in out] == ["active"]
        out_all = repo.list_under(
            version_id="v1.0.0",
            level=0,
            parent_path="",
            only_active=False,
        )
        assert {e.class_slug for e in out_all} == {"active", "dead"}


class TestFindBySlug:
    def test_finds_existing(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(bit_index=3, class_slug="task"))
        out = repo.find_by_slug(
            version_id="v1.0.0", level=0, parent_path="", class_slug="task"
        )
        assert out is not None
        assert out.bit_index == 3

    def test_returns_none_for_missing(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        out = repo.find_by_slug(
            version_id="v1.0.0", level=0, parent_path="", class_slug="missing"
        )
        assert out is None


class TestFreeSlots:
    def test_all_free_initially(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        free = repo.free_slots_under(
            version_id="v1.0.0", level=0, parent_path=""
        )
        assert free == list(range(10))

    def test_some_occupied(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        for i, slug in enumerate(["task", "schema", "analytics"]):
            repo.create(_entry(bit_index=i, class_slug=slug))
        free = repo.free_slots_under(
            version_id="v1.0.0", level=0, parent_path=""
        )
        assert free == [3, 4, 5, 6, 7, 8, 9]

    def test_deprecated_slot_counts_as_free(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(bit_index=0, class_slug="task"))
        repo.create(
            _entry(
                bit_index=1,
                class_slug="dead",
                status=TaxonomyBitStatus.DEPRECATED_MERGED,
                merged_into_slug="task",
            )
        )
        free = repo.free_slots_under(
            version_id="v1.0.0", level=0, parent_path=""
        )
        # bit 0 occupied (active), bit 1 free (deprecated не считается)
        assert 0 not in free
        assert 1 in free


class TestIncrementUsage:
    def test_increment(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        repo.create(_entry(bit_index=0, class_slug="task"))
        repo.increment_usage(
            version_id="v1.0.0", level=0, parent_path="", bit_index=0
        )
        repo.increment_usage(
            version_id="v1.0.0", level=0, parent_path="", bit_index=0
        )
        out = repo.get(
            version_id="v1.0.0", level=0, parent_path="", bit_index=0
        )
        assert out.usage_count == 2

    def test_increment_missing_rejected(self) -> None:
        repo = InMemoryTaxonomyEntryRepository()
        with pytest.raises(RegistryEntryNotFoundError):
            repo.increment_usage(
                version_id="v1.0.0", level=0, parent_path="", bit_index=5
            )
