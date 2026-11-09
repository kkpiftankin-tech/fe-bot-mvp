"""Component-тесты TaxonomyRegistry (SETUP-12 / T-S12-010).

Покрывает: bootstrap из seed → активная версия → list_under, find_by_slug,
free_slots, increment_usage, patch-bump, advisory-lock.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)

from fe_bot.taxonomy import (
    NoActiveTaxonomyVersionError,
    TaxonomyRegistry,
    load_seed_taxonomy,
)

pytestmark = pytest.mark.component


def _seed_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "seed"
        / "taxonomy"
        / "v1_0_0.yaml"
    )


def _entry(
    *,
    version_id: str = "v1.0.0",
    level: int = 0,
    parent_path: str = "",
    bit_index: int,
    class_slug: str,
    **overrides: object,
) -> TaxonomyBitRegistryEntry:
    defaults: dict[str, object] = {
        "version_id": version_id,
        "level": level,
        "parent_path": parent_path,
        "bit_index": bit_index,
        "class_slug": class_slug,
        "display_name_ru": f"Класс {class_slug}",
        "description": f"Описание {class_slug}.",
        "created_at": datetime.now(tz=UTC),
        "auto_created": True,
    }
    defaults.update(overrides)
    return TaxonomyBitRegistryEntry(**defaults)  # type: ignore[arg-type]


class TestBootstrap:
    def test_active_version_raises_without_bootstrap(self) -> None:
        reg = TaxonomyRegistry()
        with pytest.raises(NoActiveTaxonomyVersionError):
            reg.get_active_version()

    def test_bootstrap_from_seed(self) -> None:
        reg = TaxonomyRegistry()
        version = load_seed_taxonomy(_seed_path())
        reg.bootstrap_from_version(version)
        active = reg.get_active_version()
        assert active.version_id == "v1.0.0"

    def test_bootstrap_loads_entries(self) -> None:
        reg = TaxonomyRegistry()
        version = load_seed_taxonomy(_seed_path())
        reg.bootstrap_from_version(version)
        l0 = reg.list_active_under(level=0, parent_path="")
        assert len(l0) == 9
        slugs = {e.class_slug for e in l0}
        assert "task" in slugs and "schema" in slugs


class TestQueries:
    def _bootstrapped(self) -> TaxonomyRegistry:
        reg = TaxonomyRegistry()
        version = load_seed_taxonomy(_seed_path())
        reg.bootstrap_from_version(version)
        return reg

    def test_list_active_under_l0(self) -> None:
        reg = self._bootstrapped()
        out = reg.list_active_under(level=0, parent_path="")
        assert len(out) == 9
        bits = [e.bit_index for e in out]
        assert bits == sorted(bits)

    def test_list_active_under_l1_empty(self) -> None:
        reg = self._bootstrapped()
        out = reg.list_active_under(level=1, parent_path="task")
        assert out == []

    def test_find_by_slug(self) -> None:
        reg = self._bootstrapped()
        entry = reg.find_by_slug(level=0, parent_path="", class_slug="task")
        assert entry is not None
        assert entry.bit_index == 0
        assert entry.doc_type_hint == "task_card"

    def test_find_by_slug_missing(self) -> None:
        reg = self._bootstrapped()
        assert (
            reg.find_by_slug(level=0, parent_path="", class_slug="nope")
            is None
        )

    def test_get_by_bit(self) -> None:
        reg = self._bootstrapped()
        entry = reg.get_by_bit(level=0, parent_path="", bit_index=0)
        assert entry.class_slug == "task"

    def test_free_slots(self) -> None:
        reg = self._bootstrapped()
        free = reg.free_slots(level=0, parent_path="")
        assert free == [9]  # only bit 9 свободен (seed имеет биты 0..8)

    def test_has_free_slot(self) -> None:
        reg = self._bootstrapped()
        assert reg.has_free_slot(level=0, parent_path="") is True
        assert reg.has_free_slot(level=1, parent_path="task") is True


class TestMutations:
    def _bootstrapped(self) -> TaxonomyRegistry:
        reg = TaxonomyRegistry()
        version = load_seed_taxonomy(_seed_path())
        reg.bootstrap_from_version(version)
        return reg

    def test_create_l1_entry(self) -> None:
        reg = self._bootstrapped()
        entry = _entry(
            level=1, parent_path="task", bit_index=0, class_slug="pvo"
        )
        reg.create_entry(entry)
        out = reg.list_active_under(level=1, parent_path="task")
        assert len(out) == 1
        assert out[0].class_slug == "pvo"

    def test_increment_usage(self) -> None:
        reg = self._bootstrapped()
        reg.increment_usage(level=0, parent_path="", bit_index=0)
        reg.increment_usage(level=0, parent_path="", bit_index=0)
        e = reg.get_by_bit(level=0, parent_path="", bit_index=0)
        assert e.usage_count == 2


class TestPatchBump:
    def _bootstrapped(self) -> TaxonomyRegistry:
        reg = TaxonomyRegistry()
        version = load_seed_taxonomy(_seed_path())
        reg.bootstrap_from_version(version)
        return reg

    def test_bump_creates_new_active(self) -> None:
        reg = self._bootstrapped()
        new_id = reg.bump_version_patch()
        assert new_id == "v1.0.1"
        assert reg.get_active_version_id() == "v1.0.1"

    def test_old_version_remains_readable(self) -> None:
        reg = self._bootstrapped()
        reg.bump_version_patch()
        # entries прежней версии всё ещё доступны
        old_entries = reg.list_active_under(
            version_id="v1.0.0", level=0, parent_path=""
        )
        assert len(old_entries) == 9

    def test_new_version_empty(self) -> None:
        reg = self._bootstrapped()
        reg.bump_version_patch()
        new_entries = reg.list_active_under(
            version_id="v1.0.1", level=0, parent_path=""
        )
        assert new_entries == []


class TestAdvisoryLock:
    def test_lock_is_reentrant(self) -> None:
        reg = TaxonomyRegistry()
        with reg.acquire_allocation_lock(
            version_id="v1.0.0", level=0, parent_path=""
        ):
            # re-acquire same key — should not deadlock (RLock)
            with reg.acquire_allocation_lock(
                version_id="v1.0.0", level=0, parent_path=""
            ):
                pass

    def test_lock_serializes_threads(self) -> None:
        reg = TaxonomyRegistry()
        events: list[str] = []
        barrier = threading.Barrier(2)

        def worker(name: str) -> None:
            barrier.wait()
            with reg.acquire_allocation_lock(
                version_id="v1.0.0", level=0, parent_path=""
            ):
                events.append(f"{name}:enter")
                # короткая «работа» внутри critical section
                events.append(f"{name}:exit")

        t1 = threading.Thread(target=worker, args=("A",))
        t2 = threading.Thread(target=worker, args=("B",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # последовательно: A:enter,A:exit,B:enter,B:exit или B,B,A,A
        assert len(events) == 4
        assert events[0].endswith(":enter")
        assert events[1].endswith(":exit")
        assert events[2].endswith(":enter")
        assert events[3].endswith(":exit")
        # один поток не пересёкся с другим
        assert events[0][0] == events[1][0]
        assert events[2][0] == events[3][0]
        assert events[0][0] != events[2][0]


class TestStats:
    def test_stats_without_active(self) -> None:
        reg = TaxonomyRegistry()
        s = reg.stats()
        assert s["active_version"] == 0
        assert s["l0_classes"] == 0

    def test_stats_after_bootstrap(self) -> None:
        reg = TaxonomyRegistry()
        version = load_seed_taxonomy(_seed_path())
        reg.bootstrap_from_version(version)
        s = reg.stats()
        assert s["active_version"] == 1
        assert s["l0_classes"] == 9
        assert s["l0_free_slots"] == 1
        assert s["l0_max"] == 10


class TestEmptyVersion:
    def test_bootstrap_empty_version(self) -> None:
        reg = TaxonomyRegistry()
        empty = TaxonomyVersion(
            version_id="v1.0.0",
            created_at=datetime.now(tz=UTC),
            entries=[],
        )
        reg.bootstrap_from_version(empty)
        assert reg.list_active_under(level=0, parent_path="") == []
        assert reg.free_slots(level=0, parent_path="") == list(range(10))
