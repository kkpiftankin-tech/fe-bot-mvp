"""ProcessingLogRepository (SETUP-03 / T-S03-007).

Хранилище SourceProcessingLogEntry с идемпотентностью по event_id и
фильтрацией по step / level / setup_job_id.

В продакшене (INF-002) — PostgreSQL с индексами по (source_document_id,
created_at), (setup_job_id, step).
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.processing_log import (
    ProcessingLogLevel,
    ProcessingLogStep,
    SourceProcessingLogEntry,
)


class ProcessingLogRepository(Protocol):
    """Append-only журнал событий обработки."""

    def append(self, entry: SourceProcessingLogEntry) -> SourceProcessingLogEntry:
        """Idempotent по event_id."""
        ...

    def list_for_document(
        self,
        source_document_id: str,
        *,
        step: ProcessingLogStep | None = None,
        level: ProcessingLogLevel | None = None,
    ) -> list[SourceProcessingLogEntry]:
        """С фильтрами по step/level."""
        ...

    def list_for_job(
        self,
        setup_job_id: str,
        *,
        level: ProcessingLogLevel | None = None,
    ) -> list[SourceProcessingLogEntry]:
        """Все события setup job (через все документы)."""
        ...

    def get_by_event_id(
        self, event_id: str
    ) -> SourceProcessingLogEntry | None: ...


class InMemoryProcessingLogRepository:
    """In-memory реализация."""

    def __init__(self) -> None:
        self._by_document: dict[str, list[SourceProcessingLogEntry]] = {}
        self._by_event: dict[str, SourceProcessingLogEntry] = {}
        self._lock = threading.Lock()

    def append(
        self, entry: SourceProcessingLogEntry
    ) -> SourceProcessingLogEntry:
        with self._lock:
            existing = self._by_event.get(entry.event_id)
            if existing is not None:
                return existing.model_copy(deep=True)
            stored = entry.model_copy(deep=True)
            self._by_event[entry.event_id] = stored
            self._by_document.setdefault(entry.source_document_id, []).append(stored)
            return stored.model_copy(deep=True)

    def list_for_document(
        self,
        source_document_id: str,
        *,
        step: ProcessingLogStep | None = None,
        level: ProcessingLogLevel | None = None,
    ) -> list[SourceProcessingLogEntry]:
        with self._lock:
            entries = self._by_document.get(source_document_id, [])
            result = entries
            if step is not None:
                result = [e for e in result if e.step == step]
            if level is not None:
                result = [e for e in result if e.level == level]
            return [e.model_copy(deep=True) for e in result]

    def list_for_job(
        self,
        setup_job_id: str,
        *,
        level: ProcessingLogLevel | None = None,
    ) -> list[SourceProcessingLogEntry]:
        with self._lock:
            result: list[SourceProcessingLogEntry] = []
            for entries in self._by_document.values():
                for entry in entries:
                    if entry.setup_job_id != setup_job_id:
                        continue
                    if level is not None and entry.level != level:
                        continue
                    result.append(entry.model_copy(deep=True))
            return result

    def get_by_event_id(
        self, event_id: str
    ) -> SourceProcessingLogEntry | None:
        with self._lock:
            entry = self._by_event.get(event_id)
            return entry.model_copy(deep=True) if entry else None

    def clear(self) -> None:
        with self._lock:
            self._by_document.clear()
            self._by_event.clear()
