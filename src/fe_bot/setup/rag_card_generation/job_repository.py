"""RAGCardGenerationJobRepository (SETUP-05 / T-S05-008).

In-memory хранилище RAGCardGenerationJob. Thread-safe через threading.Lock,
deep-copy на чтение. ``get_active_for_setup_job`` нужен orchestrator'у, чтобы
не запускать второй job для уже активного setup_job_id (409
RAG_CARD_GENERATION_ALREADY_RUNNING).

Поддерживает snapshot/restore через SnapshotPersister (dev-only JSON).
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.rag_card_generation_job import (
    RAGCardGenerationJob,
    RAGCardGenerationJobStatus,
)

_ACTIVE_STATUSES = frozenset(
    {
        RAGCardGenerationJobStatus.CREATED,
        RAGCardGenerationJobStatus.QUEUED,
        RAGCardGenerationJobStatus.RUNNING,
    }
)


class DuplicateRAGCardGenerationJobError(ValueError):
    def __init__(self, generation_job_id: str) -> None:
        self.generation_job_id = generation_job_id
        super().__init__(f"RAGCardGenerationJob already exists: {generation_job_id}")


class RAGCardGenerationJobNotFoundError(LookupError):
    def __init__(self, generation_job_id: str) -> None:
        self.generation_job_id = generation_job_id
        super().__init__(f"RAGCardGenerationJob not found: {generation_job_id}")


class RAGCardGenerationJobRepository(Protocol):
    def create(self, job: RAGCardGenerationJob) -> None: ...

    def get(self, generation_job_id: str) -> RAGCardGenerationJob: ...

    def update(self, job: RAGCardGenerationJob) -> None: ...

    def list_for_setup_job(self, setup_job_id: str) -> list[RAGCardGenerationJob]: ...

    def get_active_for_setup_job(self, setup_job_id: str) -> RAGCardGenerationJob | None: ...


class InMemoryRAGCardGenerationJobRepository:
    """In-memory реализация (MVP)."""

    def __init__(self) -> None:
        self._store: dict[str, RAGCardGenerationJob] = {}
        self._lock = threading.Lock()

    def create(self, job: RAGCardGenerationJob) -> None:
        with self._lock:
            if job.generation_job_id in self._store:
                raise DuplicateRAGCardGenerationJobError(job.generation_job_id)
            self._store[job.generation_job_id] = job.model_copy(deep=True)

    def get(self, generation_job_id: str) -> RAGCardGenerationJob:
        with self._lock:
            if generation_job_id not in self._store:
                raise RAGCardGenerationJobNotFoundError(generation_job_id)
            return self._store[generation_job_id].model_copy(deep=True)

    def update(self, job: RAGCardGenerationJob) -> None:
        with self._lock:
            if job.generation_job_id not in self._store:
                raise RAGCardGenerationJobNotFoundError(job.generation_job_id)
            self._store[job.generation_job_id] = job.model_copy(deep=True)

    def list_for_setup_job(self, setup_job_id: str) -> list[RAGCardGenerationJob]:
        with self._lock:
            return [
                j.model_copy(deep=True)
                for j in self._store.values()
                if j.setup_job_id == setup_job_id
            ]

    def get_active_for_setup_job(self, setup_job_id: str) -> RAGCardGenerationJob | None:
        with self._lock:
            for job in self._store.values():
                if job.setup_job_id == setup_job_id and job.status in _ACTIVE_STATUSES:
                    return job.model_copy(deep=True)
            return None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    # ----- Snapshot persistence (dev-only) -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {gid: j.model_dump(mode="json") for gid, j in self._store.items()}

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._store.clear()
            for gid, raw in data.items():
                self._store[gid] = RAGCardGenerationJob.model_validate(raw)
