"""TaxonomyEntryRepository (SETUP-12 / T-S12-011).

In-memory хранилище ``TaxonomyBitRegistryEntry``. Поддерживает запросы
для auto-allocator'а и LLMClassifier'а (list_under, find_by_slug,
free_slots_under).
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.taxonomy.registry import (
    MAX_BITS_PER_LEVEL,
    TaxonomyBitRegistryEntry,
    TaxonomyBitStatus,
)


class DuplicateRegistryEntryError(ValueError):
    def __init__(
        self,
        version_id: str,
        level: int,
        parent_path: str,
        bit_index: int | None = None,
        class_slug: str | None = None,
    ) -> None:
        self.version_id = version_id
        self.level = level
        self.parent_path = parent_path
        self.bit_index = bit_index
        self.class_slug = class_slug
        detail = (
            f"bit_index={bit_index}"
            if bit_index is not None
            else f"class_slug={class_slug!r}"
        )
        super().__init__(
            f"Registry entry already exists: version={version_id} "
            f"level={level} parent_path={parent_path!r} {detail}"
        )


class RegistryEntryNotFoundError(LookupError):
    def __init__(
        self,
        version_id: str,
        level: int,
        parent_path: str,
        bit_index: int,
    ) -> None:
        self.version_id = version_id
        self.level = level
        self.parent_path = parent_path
        self.bit_index = bit_index
        super().__init__(
            f"Registry entry not found: version={version_id} "
            f"level={level} parent_path={parent_path!r} bit={bit_index}"
        )


class TaxonomyEntryRepository(Protocol):
    def create(self, entry: TaxonomyBitRegistryEntry) -> None: ...
    def update(self, entry: TaxonomyBitRegistryEntry) -> None: ...
    def get(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        bit_index: int,
    ) -> TaxonomyBitRegistryEntry: ...
    def list_under(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        only_active: bool = True,
    ) -> list[TaxonomyBitRegistryEntry]: ...
    def find_by_slug(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        class_slug: str,
    ) -> TaxonomyBitRegistryEntry | None: ...
    def free_slots_under(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
    ) -> list[int]: ...
    def increment_usage(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        bit_index: int,
    ) -> None: ...


class InMemoryTaxonomyEntryRepository:
    """In-memory реализация. Хранит entries в dict с composite ключом."""

    def __init__(self) -> None:
        # Key: (version_id, level, parent_path, bit_index)
        self._store: dict[tuple[str, int, str, int], TaxonomyBitRegistryEntry] = {}
        # Secondary index для find_by_slug: (version, level, parent, slug) → bit_index
        self._slug_index: dict[tuple[str, int, str, str], int] = {}
        self._lock = threading.Lock()

    def create(self, entry: TaxonomyBitRegistryEntry) -> None:
        with self._lock:
            self._create_locked(entry)

    def _create_locked(self, entry: TaxonomyBitRegistryEntry) -> None:
        key = (
            entry.version_id,
            entry.level,
            entry.parent_path,
            entry.bit_index,
        )
        slug_key = (
            entry.version_id,
            entry.level,
            entry.parent_path,
            entry.class_slug,
        )
        if key in self._store:
            raise DuplicateRegistryEntryError(
                entry.version_id,
                entry.level,
                entry.parent_path,
                bit_index=entry.bit_index,
            )
        if slug_key in self._slug_index:
            raise DuplicateRegistryEntryError(
                entry.version_id,
                entry.level,
                entry.parent_path,
                class_slug=entry.class_slug,
            )
        self._store[key] = entry.model_copy(deep=True)
        self._slug_index[slug_key] = entry.bit_index

    def update(self, entry: TaxonomyBitRegistryEntry) -> None:
        with self._lock:
            key = (
                entry.version_id,
                entry.level,
                entry.parent_path,
                entry.bit_index,
            )
            if key not in self._store:
                raise RegistryEntryNotFoundError(
                    entry.version_id,
                    entry.level,
                    entry.parent_path,
                    entry.bit_index,
                )
            old = self._store[key]
            if old.class_slug != entry.class_slug:
                self._slug_index.pop(
                    (
                        old.version_id,
                        old.level,
                        old.parent_path,
                        old.class_slug,
                    ),
                    None,
                )
                slug_key = (
                    entry.version_id,
                    entry.level,
                    entry.parent_path,
                    entry.class_slug,
                )
                if slug_key in self._slug_index:
                    raise DuplicateRegistryEntryError(
                        entry.version_id,
                        entry.level,
                        entry.parent_path,
                        class_slug=entry.class_slug,
                    )
                self._slug_index[slug_key] = entry.bit_index
            self._store[key] = entry.model_copy(deep=True)

    def get(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        bit_index: int,
    ) -> TaxonomyBitRegistryEntry:
        with self._lock:
            key = (version_id, level, parent_path, bit_index)
            if key not in self._store:
                raise RegistryEntryNotFoundError(
                    version_id, level, parent_path, bit_index
                )
            return self._store[key].model_copy(deep=True)

    def list_under(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        only_active: bool = True,
    ) -> list[TaxonomyBitRegistryEntry]:
        with self._lock:
            out: list[TaxonomyBitRegistryEntry] = []
            for (vid, lv, pp, _bit), entry in self._store.items():
                if vid != version_id or lv != level or pp != parent_path:
                    continue
                if only_active and entry.status != TaxonomyBitStatus.ACTIVE:
                    continue
                out.append(entry.model_copy(deep=True))
            out.sort(key=lambda e: e.bit_index)
            return out

    def find_by_slug(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        class_slug: str,
    ) -> TaxonomyBitRegistryEntry | None:
        with self._lock:
            slug_key = (version_id, level, parent_path, class_slug)
            if slug_key not in self._slug_index:
                return None
            bit = self._slug_index[slug_key]
            key = (version_id, level, parent_path, bit)
            return self._store[key].model_copy(deep=True)

    def free_slots_under(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
    ) -> list[int]:
        with self._lock:
            occupied = {
                bit
                for (vid, lv, pp, bit), entry in self._store.items()
                if vid == version_id
                and lv == level
                and pp == parent_path
                and entry.status == TaxonomyBitStatus.ACTIVE
            }
            return [b for b in range(MAX_BITS_PER_LEVEL) if b not in occupied]

    def increment_usage(
        self,
        *,
        version_id: str,
        level: int,
        parent_path: str,
        bit_index: int,
    ) -> None:
        with self._lock:
            key = (version_id, level, parent_path, bit_index)
            if key not in self._store:
                raise RegistryEntryNotFoundError(
                    version_id, level, parent_path, bit_index
                )
            old = self._store[key]
            self._store[key] = old.model_copy(
                update={"usage_count": old.usage_count + 1}
            )
