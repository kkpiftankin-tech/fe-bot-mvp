"""TaxonomyRegistry (SETUP-12 / T-S12-010).

Фасад поверх ``TaxonomyVersionRepository`` + ``TaxonomyEntryRepository``,
предоставляющий operational-API для:

- Bootstrap из seed-YAML.
- Чтения активной версии и её entries.
- Поиска кандидатов под parent_path (для LLM-prompt'а).
- Поиска свободных слотов (для auto-allocator'а в S2).
- Поиска по slug'у (для similarity-gate dedup).
- Atomic patch-bump'а версии при auto-create нового класса.
- Incrementing usage_count при выставлении бита.

Concurrency: per-(version, level, parent_path) advisory-lock через
threading.RLock dict — защищает auto-allocator от race condition'ов.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from schemas.taxonomy.registry import (
    MAX_BITS_PER_LEVEL,
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)

from fe_bot.taxonomy.entry_repository import (
    InMemoryTaxonomyEntryRepository,
    TaxonomyEntryRepository,
)
from fe_bot.taxonomy.exceptions import NoActiveTaxonomyVersionError
from fe_bot.taxonomy.version_repository import (
    InMemoryTaxonomyVersionRepository,
    TaxonomyVersionRepository,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class TaxonomyRegistry:
    """Фасад над двумя репозиториями + lock-фабрика для auto-allocator'а."""

    def __init__(
        self,
        *,
        version_repo: TaxonomyVersionRepository | None = None,
        entry_repo: TaxonomyEntryRepository | None = None,
    ) -> None:
        self._versions = version_repo or InMemoryTaxonomyVersionRepository()
        self._entries = entry_repo or InMemoryTaxonomyEntryRepository()
        # Per-(version, level, parent_path) advisory-локи.
        self._locks: dict[tuple[str, int, str], threading.RLock] = {}
        self._locks_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap_from_version(self, version: TaxonomyVersion) -> None:
        """Загружает версию (обычно из seed-loader'а) и делает её активной.

        Все entries версии вставляются в entry-repo.
        Уже существующая версия с тем же version_id — это ошибка
        (DuplicateTaxonomyVersionError).
        """
        version_no_entries = version.model_copy(update={"entries": []})
        self._versions.create(version_no_entries)
        for entry in version.entries:
            self._entries.create(entry)

    # ------------------------------------------------------------------
    # Active version accessors
    # ------------------------------------------------------------------

    def get_active_version(self) -> TaxonomyVersion:
        active = self._versions.get_active()
        if active is None:
            raise NoActiveTaxonomyVersionError(
                "No active TaxonomyVersion in repository; bootstrap missing?"
            )
        return active

    def get_active_version_id(self) -> str:
        return self.get_active_version().version_id

    # ------------------------------------------------------------------
    # Entries
    # ------------------------------------------------------------------

    def list_active_under(
        self,
        *,
        version_id: str | None = None,
        level: int,
        parent_path: str,
    ) -> list[TaxonomyBitRegistryEntry]:
        """Список активных классов под parent_path.

        Если version_id не указан — используется активная версия.
        """
        vid = version_id or self.get_active_version_id()
        return self._entries.list_under(
            version_id=vid,
            level=level,
            parent_path=parent_path,
            only_active=True,
        )

    def get_by_bit(
        self,
        *,
        version_id: str | None = None,
        level: int,
        parent_path: str,
        bit_index: int,
    ) -> TaxonomyBitRegistryEntry:
        vid = version_id or self.get_active_version_id()
        return self._entries.get(
            version_id=vid,
            level=level,
            parent_path=parent_path,
            bit_index=bit_index,
        )

    def find_by_slug(
        self,
        *,
        version_id: str | None = None,
        level: int,
        parent_path: str,
        class_slug: str,
    ) -> TaxonomyBitRegistryEntry | None:
        vid = version_id or self.get_active_version_id()
        return self._entries.find_by_slug(
            version_id=vid,
            level=level,
            parent_path=parent_path,
            class_slug=class_slug,
        )

    def free_slots(
        self,
        *,
        version_id: str | None = None,
        level: int,
        parent_path: str,
    ) -> list[int]:
        vid = version_id or self.get_active_version_id()
        return self._entries.free_slots_under(
            version_id=vid,
            level=level,
            parent_path=parent_path,
        )

    def has_free_slot(
        self,
        *,
        version_id: str | None = None,
        level: int,
        parent_path: str,
    ) -> bool:
        return bool(
            self.free_slots(
                version_id=version_id,
                level=level,
                parent_path=parent_path,
            )
        )

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create_entry(self, entry: TaxonomyBitRegistryEntry) -> None:
        """Регистрирует новый класс. Используется auto-allocator'ом."""
        self._entries.create(entry)

    def update_entry(self, entry: TaxonomyBitRegistryEntry) -> None:
        self._entries.update(entry)

    def increment_usage(
        self,
        *,
        version_id: str | None = None,
        level: int,
        parent_path: str,
        bit_index: int,
    ) -> None:
        vid = version_id or self.get_active_version_id()
        self._entries.increment_usage(
            version_id=vid,
            level=level,
            parent_path=parent_path,
            bit_index=bit_index,
        )

    # ------------------------------------------------------------------
    # Version bump
    # ------------------------------------------------------------------

    def bump_version_patch(self) -> str:
        """Patch-bump активной версии.

        Текущая активная остаётся в реестре (становится inactive); новая
        version_id с patch+1 создаётся как активная. Entries активной
        версии **не копируются** — они продолжают принадлежать прежней
        версии. Auto-allocator при создании нового класса использует
        новую активную version_id.

        Это позволяет старым ParsedSection с прежним taxonomy_version_id
        корректно читать свои биты (registry хранит обе версии).

        Returns:
            Новый active version_id (например, "v1.0.1").
        """
        active = self.get_active_version()
        new_id = _next_patch(active.version_id)
        new_version = TaxonomyVersion(
            version_id=new_id,
            created_at=datetime.now(tz=UTC),
            description=(
                f"Auto patch-bump from {active.version_id} "
                "(triggered by auto-allocator)."
            ),
            is_active=True,
            entries=[],
        )
        self._versions.create(new_version)
        return new_id

    # ------------------------------------------------------------------
    # Concurrency primitives
    # ------------------------------------------------------------------

    @contextmanager
    def acquire_allocation_lock(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
    ) -> Iterator[None]:
        """Per-(version, level, parent_path) advisory-lock.

        Используется auto-allocator'ом для предотвращения race condition'ов
        при concurrent NEW-предложениях LLM под одним parent_path.
        """
        key = (version_id, level, parent_path)
        with self._locks_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._locks[key] = lock
        with lock:
            yield

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, int]:
        """Возвращает базовую статистику для health-чеков."""
        try:
            active = self.get_active_version()
        except NoActiveTaxonomyVersionError:
            return {"active_version": 0, "l0_classes": 0}
        l0_entries = self._entries.list_under(
            version_id=active.version_id,
            level=0,
            parent_path="",
            only_active=True,
        )
        return {
            "active_version": 1,
            "l0_classes": len(l0_entries),
            "l0_free_slots": len(
                self.free_slots(level=0, parent_path="")
            ),
            "l0_max": MAX_BITS_PER_LEVEL,
        }


def _next_patch(version_id: str) -> str:
    """v1.2.3 → v1.2.4."""
    if not version_id.startswith("v"):
        raise ValueError(f"Invalid version_id: {version_id}")
    parts = version_id[1:].split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semver: {version_id}")
    major, minor, patch = (int(p) for p in parts)
    return f"v{major}.{minor}.{patch + 1}"
