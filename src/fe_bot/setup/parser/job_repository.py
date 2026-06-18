"""ParseJobRepository (SETUP-04 / T-S04-006).

In-memory хранилище ParseJob. Thread-safe через threading.Lock,
deep-copy на чтение. В продакшене (INF-002) заменится на PostgreSQL.

Idempotency: `get_active_for_setup_job` нужен оркестратору, чтобы
не запускать второй ParseJob для уже активного setup_job_id
(возвращает 409 PARSE_JOB_ALREADY_RUNNING).
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.parse_job import ParseJob, ParseJobStatus

_ACTIVE_STATUSES = frozenset(
    {ParseJobStatus.CREATED, ParseJobStatus.QUEUED, ParseJobStatus.RUNNING}
)


class DuplicateParseJobError(ValueError):
    def __init__(self, parse_job_id: str) -> None:
        self.parse_job_id = parse_job_id
        super().__init__(f"ParseJob already exists: {parse_job_id}")


class ParseJobNotFoundError(LookupError):
    def __init__(self, parse_job_id: str) -> None:
        self.parse_job_id = parse_job_id
        super().__init__(f"ParseJob not found: {parse_job_id}")


class ParseJobRepository(Protocol):
    """Контракт хранилища ParseJob."""

    def create(self, job: ParseJob) -> None: ...

    def get(self, parse_job_id: str) -> ParseJob: ...

    def update(self, job: ParseJob) -> None: ...

    def list_for_setup_job(self, setup_job_id: str) -> list[ParseJob]: ...

    def get_active_for_setup_job(self, setup_job_id: str) -> ParseJob | None: ...


class InMemoryParseJobRepository:
    """In-memory реализация (MVP)."""

    def __init__(self) -> None:
        self._store: dict[str, ParseJob] = {}
        self._lock = threading.Lock()

    def create(self, job: ParseJob) -> None:
        with self._lock:
            if job.parse_job_id in self._store:
                raise DuplicateParseJobError(job.parse_job_id)
            self._store[job.parse_job_id] = job.model_copy(deep=True)

    def get(self, parse_job_id: str) -> ParseJob:
        with self._lock:
            if parse_job_id not in self._store:
                raise ParseJobNotFoundError(parse_job_id)
            return self._store[parse_job_id].model_copy(deep=True)

    def update(self, job: ParseJob) -> None:
        with self._lock:
            if job.parse_job_id not in self._store:
                raise ParseJobNotFoundError(job.parse_job_id)
            self._store[job.parse_job_id] = job.model_copy(deep=True)

    def list_for_setup_job(self, setup_job_id: str) -> list[ParseJob]:
        with self._lock:
            return [
                j.model_copy(deep=True)
                for j in self._store.values()
                if j.setup_job_id == setup_job_id
            ]

    def get_active_for_setup_job(self, setup_job_id: str) -> ParseJob | None:
        with self._lock:
            for job in self._store.values():
                if job.setup_job_id == setup_job_id and job.status in _ACTIVE_STATUSES:
                    return job.model_copy(deep=True)
            return None

    def clear(self) -> None:
        """Для тестов."""
        with self._lock:
            self._store.clear()
