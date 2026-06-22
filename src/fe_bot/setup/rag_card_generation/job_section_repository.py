"""RAGCardGenerationJobSectionRepository (SETUP-05 / T-S05-009).

Per-section отслеживание внутри RAGCardGenerationJob. Уникальный ключ —
generation_job_section_id. ``list_pending_for_job`` возвращает только PENDING.
``find_existing_doc_id`` — для DOC_ID_CONFLICT detection.

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.rag_card_generation_job_section import (
    RAGCardGenerationJobSection,
    RAGCardGenerationJobSectionStatus,
)


class DuplicateGenerationJobSectionError(ValueError):
    def __init__(self, generation_job_section_id: str) -> None:
        self.generation_job_section_id = generation_job_section_id
        super().__init__(f"RAGCardGenerationJobSection already exists: {generation_job_section_id}")


class GenerationJobSectionNotFoundError(LookupError):
    def __init__(self, generation_job_section_id: str) -> None:
        self.generation_job_section_id = generation_job_section_id
        super().__init__(f"RAGCardGenerationJobSection not found: {generation_job_section_id}")


class RAGCardGenerationJobSectionRepository(Protocol):
    def add(self, section: RAGCardGenerationJobSection) -> None: ...

    def get(self, generation_job_section_id: str) -> RAGCardGenerationJobSection: ...

    def update(self, section: RAGCardGenerationJobSection) -> None: ...

    def list_for_job(self, generation_job_id: str) -> list[RAGCardGenerationJobSection]: ...

    def list_pending_for_job(self, generation_job_id: str) -> list[RAGCardGenerationJobSection]: ...

    def find_existing_doc_id(self, doc_id: str) -> RAGCardGenerationJobSection | None: ...


class InMemoryRAGCardGenerationJobSectionRepository:
    """In-memory реализация. Insertion-order preservation для list_*_for_job."""

    def __init__(self) -> None:
        self._store: dict[str, RAGCardGenerationJobSection] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def add(self, section: RAGCardGenerationJobSection) -> None:
        with self._lock:
            if section.generation_job_section_id in self._store:
                raise DuplicateGenerationJobSectionError(section.generation_job_section_id)
            self._store[section.generation_job_section_id] = section.model_copy(deep=True)
            self._order.append(section.generation_job_section_id)

    def get(self, generation_job_section_id: str) -> RAGCardGenerationJobSection:
        with self._lock:
            if generation_job_section_id not in self._store:
                raise GenerationJobSectionNotFoundError(generation_job_section_id)
            return self._store[generation_job_section_id].model_copy(deep=True)

    def update(self, section: RAGCardGenerationJobSection) -> None:
        with self._lock:
            if section.generation_job_section_id not in self._store:
                raise GenerationJobSectionNotFoundError(section.generation_job_section_id)
            self._store[section.generation_job_section_id] = section.model_copy(deep=True)

    def list_for_job(self, generation_job_id: str) -> list[RAGCardGenerationJobSection]:
        with self._lock:
            return [
                self._store[sid].model_copy(deep=True)
                for sid in self._order
                if self._store[sid].generation_job_id == generation_job_id
            ]

    def list_pending_for_job(self, generation_job_id: str) -> list[RAGCardGenerationJobSection]:
        with self._lock:
            return [
                self._store[sid].model_copy(deep=True)
                for sid in self._order
                if self._store[sid].generation_job_id == generation_job_id
                and self._store[sid].status == RAGCardGenerationJobSectionStatus.PENDING
            ]

    def find_existing_doc_id(self, doc_id: str) -> RAGCardGenerationJobSection | None:
        with self._lock:
            for section in self._store.values():
                if section.generated_doc_id == doc_id:
                    return section.model_copy(deep=True)
            return None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()

    # ----- Snapshot persistence -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "sections": {sid: s.model_dump(mode="json") for sid, s in self._store.items()},
                "order": list(self._order),
            }

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()
            sections = data.get("sections", {})
            order = data.get("order", [])
            if isinstance(sections, dict):
                for sid, raw in sections.items():
                    self._store[sid] = RAGCardGenerationJobSection.model_validate(raw)
            if isinstance(order, list):
                self._order.extend(i for i in order if isinstance(i, str))
