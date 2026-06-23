"""RAGCardVersionRepository (SETUP-06 / T-S06-009).

Хранит версии RAG-карточек. Уникальность ``(doc_id, card_version)``.
Только одна версия per doc_id с ``is_current=True``.

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.rag_card_version import RAGCardVersionDTO


class CardVersionAlreadyExistsError(ValueError):
    def __init__(self, doc_id: str, card_version: str) -> None:
        self.doc_id = doc_id
        self.card_version = card_version
        super().__init__(f"Card version {doc_id!r}/{card_version!r} already exists")


class CardVersionNotFoundError(KeyError):
    def __init__(self, doc_id: str, card_version: str) -> None:
        self.doc_id = doc_id
        self.card_version = card_version
        super().__init__(f"Card version {doc_id!r}/{card_version!r} not found")


class RAGCardVersionRepository(Protocol):
    def add(self, version: RAGCardVersionDTO) -> RAGCardVersionDTO: ...

    def get(self, doc_id: str, card_version: str) -> RAGCardVersionDTO: ...

    def list_for_card(self, doc_id: str) -> list[RAGCardVersionDTO]: ...

    def current(self, doc_id: str) -> RAGCardVersionDTO | None: ...

    def set_current(self, doc_id: str, card_version: str) -> None: ...

    def mark_deprecated(self, doc_id: str, card_version: str) -> None: ...


class InMemoryRAGCardVersionRepository:
    """In-memory + thread-safe + uniqueness + single-current invariant."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], RAGCardVersionDTO] = {}
        self._lock = threading.Lock()

    def add(self, version: RAGCardVersionDTO) -> RAGCardVersionDTO:
        key = (version.doc_id, version.card_version)
        with self._lock:
            if key in self._by_key:
                raise CardVersionAlreadyExistsError(version.doc_id, version.card_version)
            if version.is_current:
                self._unset_current_locked(version.doc_id)
            self._by_key[key] = version
            return version

    def get(self, doc_id: str, card_version: str) -> RAGCardVersionDTO:
        with self._lock:
            try:
                return self._by_key[(doc_id, card_version)]
            except KeyError as exc:
                raise CardVersionNotFoundError(doc_id, card_version) from exc

    def list_for_card(self, doc_id: str) -> list[RAGCardVersionDTO]:
        with self._lock:
            return [v for (did, _), v in self._by_key.items() if did == doc_id]

    def current(self, doc_id: str) -> RAGCardVersionDTO | None:
        with self._lock:
            for (did, _), v in self._by_key.items():
                if did == doc_id and v.is_current:
                    return v
            return None

    def set_current(self, doc_id: str, card_version: str) -> None:
        key = (doc_id, card_version)
        with self._lock:
            target = self._by_key.get(key)
            if target is None:
                raise CardVersionNotFoundError(doc_id, card_version)
            self._unset_current_locked(doc_id)
            self._by_key[key] = target.model_copy(update={"is_current": True})

    def mark_deprecated(self, doc_id: str, card_version: str) -> None:
        from schemas.rag.rag_card import CardStatus

        key = (doc_id, card_version)
        with self._lock:
            target = self._by_key.get(key)
            if target is None:
                raise CardVersionNotFoundError(doc_id, card_version)
            self._by_key[key] = target.model_copy(
                update={"status": CardStatus.DEPRECATED, "is_current": False}
            )

    def _unset_current_locked(self, doc_id: str) -> None:
        # caller holds lock
        for (did, ver), v in list(self._by_key.items()):
            if did == doc_id and v.is_current:
                self._by_key[(did, ver)] = v.model_copy(update={"is_current": False})

    def clear(self) -> None:
        with self._lock:
            self._by_key.clear()

    # ----- Snapshot -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                f"{doc_id}::{ver}": v.model_dump(mode="json")
                for (doc_id, ver), v in self._by_key.items()
            }

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._by_key.clear()
            for raw in data.values():
                v = RAGCardVersionDTO.model_validate(raw)
                self._by_key[(v.doc_id, v.card_version)] = v
