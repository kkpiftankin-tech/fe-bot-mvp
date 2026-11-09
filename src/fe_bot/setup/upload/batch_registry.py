"""BatchRegistry (T-S02-008).

Хранит UploadBatch-записи для трассировки multi-file операций.
В MVP — in-memory; PostgreSQL-репозиторий подменится в INF-002 без изменения
зависимых сервисов.

Зачем хранить отдельно от idempotency cache:
- idempotency cache хранит **готовый response** (TTL 1h) для повтора.
- BatchRegistry хранит **факт batch'а** для audit / analytics / GET-history,
  не зависит от TTL.

Compound queries:
- `get_by_request_id` — для idempotency-проверки на уровне регистра
  (когда cache очищен, но batch уже существует).
- `list_for_job` — для отчёта по setup_job_id.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.upload_batch import UploadBatch


class BatchNotFoundError(LookupError):
    def __init__(self, upload_batch_id: str) -> None:
        self.upload_batch_id = upload_batch_id
        super().__init__(f"UploadBatch not found: {upload_batch_id!r}")


class BatchAlreadyExistsError(ValueError):
    def __init__(self, upload_batch_id: str) -> None:
        self.upload_batch_id = upload_batch_id
        super().__init__(f"UploadBatch already registered: {upload_batch_id!r}")


class BatchRegistry(Protocol):
    def add(self, batch: UploadBatch) -> None: ...

    def get(self, upload_batch_id: str) -> UploadBatch: ...

    def update(self, batch: UploadBatch) -> None: ...

    def list_for_job(self, setup_job_id: str) -> list[UploadBatch]: ...

    def get_by_request_id(
        self, setup_job_id: str, upload_request_id: str
    ) -> UploadBatch | None: ...


class InMemoryBatchRegistry:
    """In-memory реализация. Thread-safe через threading.Lock."""

    def __init__(self) -> None:
        self._store: dict[str, UploadBatch] = {}
        self._lock = threading.Lock()

    def add(self, batch: UploadBatch) -> None:
        with self._lock:
            if batch.upload_batch_id in self._store:
                raise BatchAlreadyExistsError(batch.upload_batch_id)
            self._store[batch.upload_batch_id] = batch.model_copy(deep=True)

    def get(self, upload_batch_id: str) -> UploadBatch:
        with self._lock:
            if upload_batch_id not in self._store:
                raise BatchNotFoundError(upload_batch_id)
            return self._store[upload_batch_id].model_copy(deep=True)

    def update(self, batch: UploadBatch) -> None:
        """Перезаписывает существующую запись. Бросает BatchNotFoundError, если нет."""
        with self._lock:
            if batch.upload_batch_id not in self._store:
                raise BatchNotFoundError(batch.upload_batch_id)
            self._store[batch.upload_batch_id] = batch.model_copy(deep=True)

    def list_for_job(self, setup_job_id: str) -> list[UploadBatch]:
        with self._lock:
            return [
                b.model_copy(deep=True)
                for b in self._store.values()
                if b.setup_job_id == setup_job_id
            ]

    def get_by_request_id(self, setup_job_id: str, upload_request_id: str) -> UploadBatch | None:
        """Линейный поиск.

        В продакшене (PostgreSQL) — индекс по (setup_job_id, upload_request_id).
        """
        with self._lock:
            for batch in self._store.values():
                if (
                    batch.setup_job_id == setup_job_id
                    and batch.upload_request_id == upload_request_id
                ):
                    return batch.model_copy(deep=True)
            return None

    def size(self) -> int:
        """Helper для тестов."""
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """Helper для тестов."""
        with self._lock:
            self._store.clear()
