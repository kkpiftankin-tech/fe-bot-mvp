"""TaxonomyVersionRepository (SETUP-12 / T-S12-011).

In-memory хранилище ``TaxonomyVersion``. Thread-safe через ``threading.Lock``,
deep-copy на чтение. Поддерживает инвариант «одна активная версия
одновременно».
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.taxonomy.registry import TaxonomyVersion


class DuplicateTaxonomyVersionError(ValueError):
    def __init__(self, version_id: str) -> None:
        self.version_id = version_id
        super().__init__(f"TaxonomyVersion already exists: {version_id}")


class TaxonomyVersionNotFoundError(LookupError):
    def __init__(self, version_id: str) -> None:
        self.version_id = version_id
        super().__init__(f"TaxonomyVersion not found: {version_id}")


class TaxonomyVersionRepository(Protocol):
    def create(self, version: TaxonomyVersion) -> None: ...
    def get(self, version_id: str) -> TaxonomyVersion: ...
    def update(self, version: TaxonomyVersion) -> None: ...
    def list_all(self) -> list[TaxonomyVersion]: ...
    def get_active(self) -> TaxonomyVersion | None: ...
    def set_active(self, version_id: str) -> None: ...


class InMemoryTaxonomyVersionRepository:
    """In-memory реализация TaxonomyVersionRepository."""

    def __init__(self) -> None:
        self._store: dict[str, TaxonomyVersion] = {}
        self._lock = threading.Lock()

    def create(self, version: TaxonomyVersion) -> None:
        with self._lock:
            if version.version_id in self._store:
                raise DuplicateTaxonomyVersionError(version.version_id)
            if version.is_active:
                self._deactivate_all_locked()
            self._store[version.version_id] = version.model_copy(deep=True)

    def get(self, version_id: str) -> TaxonomyVersion:
        with self._lock:
            if version_id not in self._store:
                raise TaxonomyVersionNotFoundError(version_id)
            return self._store[version_id].model_copy(deep=True)

    def update(self, version: TaxonomyVersion) -> None:
        with self._lock:
            if version.version_id not in self._store:
                raise TaxonomyVersionNotFoundError(version.version_id)
            if version.is_active:
                self._deactivate_all_locked(skip=version.version_id)
            self._store[version.version_id] = version.model_copy(deep=True)

    def list_all(self) -> list[TaxonomyVersion]:
        with self._lock:
            return [v.model_copy(deep=True) for v in self._store.values()]

    def get_active(self) -> TaxonomyVersion | None:
        with self._lock:
            for version in self._store.values():
                if version.is_active:
                    return version.model_copy(deep=True)
            return None

    def set_active(self, version_id: str) -> None:
        with self._lock:
            if version_id not in self._store:
                raise TaxonomyVersionNotFoundError(version_id)
            self._deactivate_all_locked(skip=version_id)
            current = self._store[version_id]
            self._store[version_id] = current.model_copy(
                update={"is_active": True}
            )

    def _deactivate_all_locked(self, *, skip: str | None = None) -> None:
        for vid, ver in list(self._store.items()):
            if vid == skip:
                continue
            if ver.is_active:
                self._store[vid] = ver.model_copy(update={"is_active": False})
