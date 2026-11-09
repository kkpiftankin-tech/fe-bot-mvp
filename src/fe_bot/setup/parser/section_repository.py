"""ParsedSectionRepository (SETUP-04 / T-S04-008).

Хранилище ParsedSection. `save_batch` — атомарный: или все секции
добавляются, или ни одна (rollback при конфликте section_id).

`find_by_content_hash` — для дедупликации при force_reparse: если
content_hash совпадает с уже сохранённой секцией, downstream может
пропустить повторную генерацию RAG-карточки.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.parsed_section import ParsedSection


class ParsedSectionNotFoundError(LookupError):
    def __init__(self, section_id: str) -> None:
        self.section_id = section_id
        super().__init__(f"ParsedSection not found: {section_id}")


class DuplicateSectionError(ValueError):
    def __init__(self, section_id: str) -> None:
        self.section_id = section_id
        super().__init__(f"ParsedSection already exists: {section_id}")


class ParsedSectionRepository(Protocol):
    def save(self, section: ParsedSection) -> None: ...

    def save_batch(self, sections: list[ParsedSection]) -> None: ...

    def get(self, section_id: str) -> ParsedSection: ...

    def list_for_document(self, source_document_id: str) -> list[ParsedSection]: ...

    def list_for_job(self, parse_job_id: str) -> list[ParsedSection]: ...

    def find_by_content_hash(self, content_hash: str) -> ParsedSection | None: ...


class InMemoryParsedSectionRepository:
    """In-memory реализация с атомарным save_batch."""

    def __init__(self) -> None:
        self._store: dict[str, ParsedSection] = {}
        # source_document_id → ordered section_ids
        self._by_document: dict[str, list[str]] = {}
        # parse_job_id → ordered section_ids
        self._by_job: dict[str, list[str]] = {}
        # content_hash → section_id (первая зарегистрированная)
        self._by_hash: dict[str, str] = {}
        self._lock = threading.Lock()

    def save(self, section: ParsedSection) -> None:
        with self._lock:
            if section.section_id in self._store:
                raise DuplicateSectionError(section.section_id)
            self._insert_locked(section)

    def save_batch(self, sections: list[ParsedSection]) -> None:
        """Атомарный batch insert.

        При конфликте section_id в любой секции batch'а — rollback
        всего batch'а (ни одна секция не сохраняется).
        """
        with self._lock:
            # Pre-check: проверяем уникальность всех ID до фактической записи.
            ids_seen: set[str] = set()
            for s in sections:
                if s.section_id in self._store or s.section_id in ids_seen:
                    raise DuplicateSectionError(s.section_id)
                ids_seen.add(s.section_id)
            # Все ID уникальны → записываем.
            for s in sections:
                self._insert_locked(s)

    def _insert_locked(self, section: ParsedSection) -> None:
        """Caller должен держать self._lock."""
        stored = section.model_copy(deep=True)
        self._store[section.section_id] = stored
        self._by_document.setdefault(section.source_document_id, []).append(section.section_id)
        self._by_job.setdefault(section.parse_job_id, []).append(section.section_id)
        # Первый zarrestrированный hash — единственный (для дедупликации).
        self._by_hash.setdefault(section.content_hash, section.section_id)

    def get(self, section_id: str) -> ParsedSection:
        with self._lock:
            if section_id not in self._store:
                raise ParsedSectionNotFoundError(section_id)
            return self._store[section_id].model_copy(deep=True)

    def list_for_document(self, source_document_id: str) -> list[ParsedSection]:
        with self._lock:
            ids = self._by_document.get(source_document_id, [])
            return [self._store[i].model_copy(deep=True) for i in ids]

    def list_for_job(self, parse_job_id: str) -> list[ParsedSection]:
        with self._lock:
            ids = self._by_job.get(parse_job_id, [])
            return [self._store[i].model_copy(deep=True) for i in ids]

    def find_by_content_hash(self, content_hash: str) -> ParsedSection | None:
        with self._lock:
            section_id = self._by_hash.get(content_hash)
            if section_id is None:
                return None
            return self._store[section_id].model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._by_document.clear()
            self._by_job.clear()
            self._by_hash.clear()

    # ----- Snapshot persistence (dev-only) -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {sid: s.model_dump(mode="json") for sid, s in self._store.items()}

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._store.clear()
            self._by_document.clear()
            self._by_job.clear()
            self._by_hash.clear()
            for raw in data.values():
                section = ParsedSection.model_validate(raw)
                self._insert_locked(section)
