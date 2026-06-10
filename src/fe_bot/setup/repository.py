"""Репозиторий setup jobs.

S1 использует in-memory реализацию. PostgreSQL-репозиторий подменится в S5/INF-002
без изменения зависимых сервисов (Protocol-интерфейс).
"""

from __future__ import annotations

from typing import Protocol

from schemas.setup.rag_setup_job import RAGSetupJob


class JobNotFoundError(LookupError):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Setup job not found: {job_id}")


class JobAlreadyExistsError(ValueError):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Setup job already exists: {job_id}")


class JobRepository(Protocol):
    """Контракт хранилища setup jobs."""

    def save(self, job: RAGSetupJob) -> None: ...

    def get(self, job_id: str) -> RAGSetupJob: ...

    def exists(self, job_id: str) -> bool: ...

    def list_by_user(self, user_id: str) -> list[RAGSetupJob]: ...


class InMemoryJobRepository:
    """In-memory реализация (MVP, для S1)."""

    def __init__(self) -> None:
        self._store: dict[str, RAGSetupJob] = {}

    def save(self, job: RAGSetupJob) -> None:
        self._store[job.setup_job_id] = job.model_copy(deep=True)

    def get(self, job_id: str) -> RAGSetupJob:
        if job_id not in self._store:
            raise JobNotFoundError(job_id)
        return self._store[job_id].model_copy(deep=True)

    def exists(self, job_id: str) -> bool:
        return job_id in self._store

    def list_by_user(self, user_id: str) -> list[RAGSetupJob]:
        return [j.model_copy(deep=True) for j in self._store.values() if j.user_id == user_id]

    def clear(self) -> None:
        """Для тестов: очистка состояния."""
        self._store.clear()
