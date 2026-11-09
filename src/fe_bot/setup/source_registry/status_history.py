"""StatusHistoryRepository (SETUP-03 / T-S03-006).

In-memory append-only хранилище SourceStatusHistoryEntry.
- Идемпотентность по event_id: повторный append с тем же event_id
  возвращает существующую запись без дубликата.
- Порядок: вставка в конец списка per-document (chronological).
- Thread-safe через threading.Lock (deep-copy на чтение).

В продакшене (INF-002) заменится на PostgreSQL с unique(event_id).
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.status_history import SourceStatusHistoryEntry


class StatusHistoryRepository(Protocol):
    """Контракт append-only хранилища status history."""

    def append(self, entry: SourceStatusHistoryEntry) -> SourceStatusHistoryEntry:
        """Добавляет запись.

        Если запись с тем же event_id уже существует — возвращает её
        (идемпотентность). Иначе сохраняет deep-copy и возвращает её.
        """
        ...

    def list_for_document(self, source_document_id: str) -> list[SourceStatusHistoryEntry]:
        """Все записи для документа в хронологическом порядке."""
        ...

    def get_by_event_id(self, event_id: str) -> SourceStatusHistoryEntry | None:
        """Поиск по event_id (для идемпотентности retry)."""
        ...

    def latest_for_document(self, source_document_id: str) -> SourceStatusHistoryEntry | None:
        """Последний переход для документа (None если истории нет)."""
        ...


class InMemoryStatusHistoryRepository:
    """In-memory реализация (MVP/тесты)."""

    def __init__(self) -> None:
        # source_document_id -> list of entries (chronological)
        self._by_document: dict[str, list[SourceStatusHistoryEntry]] = {}
        # event_id -> entry (для idempotency lookup)
        self._by_event: dict[str, SourceStatusHistoryEntry] = {}
        self._lock = threading.Lock()

    def append(self, entry: SourceStatusHistoryEntry) -> SourceStatusHistoryEntry:
        with self._lock:
            existing = self._by_event.get(entry.event_id)
            if existing is not None:
                # Idempotency: возвращаем уже сохранённую запись.
                return existing.model_copy(deep=True)
            stored = entry.model_copy(deep=True)
            self._by_event[entry.event_id] = stored
            self._by_document.setdefault(entry.source_document_id, []).append(stored)
            return stored.model_copy(deep=True)

    def list_for_document(self, source_document_id: str) -> list[SourceStatusHistoryEntry]:
        with self._lock:
            entries = self._by_document.get(source_document_id, [])
            return [e.model_copy(deep=True) for e in entries]

    def get_by_event_id(self, event_id: str) -> SourceStatusHistoryEntry | None:
        with self._lock:
            entry = self._by_event.get(event_id)
            return entry.model_copy(deep=True) if entry else None

    def latest_for_document(self, source_document_id: str) -> SourceStatusHistoryEntry | None:
        with self._lock:
            entries = self._by_document.get(source_document_id, [])
            if not entries:
                return None
            return entries[-1].model_copy(deep=True)

    def clear(self) -> None:
        """Для тестов."""
        with self._lock:
            self._by_document.clear()
            self._by_event.clear()
