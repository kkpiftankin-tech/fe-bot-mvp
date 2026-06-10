"""Idempotency cache для upload-flow (T-S02-007).

Поведение:
- caller передаёт `upload_request_id` (UUID-подобная строка).
- если cache содержит ответ для этого id → возвращает кешированный response,
  upload **не запускается** повторно.
- TTL по умолчанию 1 час; expired записи удаляются лениво при следующем доступе.

Thread-safety: in-memory implementation использует threading.Lock.
В продакшене заменяется на Redis с TTL.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fe_bot.api.setup.dto import UploadDocumentsResponse

# TTL idempotency-кэша по умолчанию.
DEFAULT_IDEMPOTENCY_TTL_SECONDS = 3600.0  # 1 hour


@dataclass(slots=True)
class _CacheEntry:
    response: UploadDocumentsResponse
    expires_at: datetime


class IdempotencyCache(Protocol):
    def get(self, key: str) -> UploadDocumentsResponse | None: ...

    def set(self, key: str, response: UploadDocumentsResponse) -> None: ...

    def clear(self) -> None: ...


class InMemoryIdempotencyCache:
    """In-memory idempotency cache.

    Ключ — `(setup_job_id, upload_request_id)` joined через `:`. Это защищает
    от cross-job collision (один и тот же upload_request_id от разных клиентов).
    """

    def __init__(
        self, *, ttl_seconds: float = DEFAULT_IDEMPOTENCY_TTL_SECONDS
    ) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, key: str) -> UploadDocumentsResponse | None:
        now = datetime.now(tz=UTC)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                # Expired — удаляем лениво.
                del self._store[key]
                return None
            return entry.response.model_copy(deep=True)

    def set(self, key: str, response: UploadDocumentsResponse) -> None:
        expires_at = datetime.now(tz=UTC) + self._ttl
        with self._lock:
            self._store[key] = _CacheEntry(
                response=response.model_copy(deep=True),
                expires_at=expires_at,
            )

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Helper для тестов."""
        with self._lock:
            return len(self._store)


def make_cache_key(setup_job_id: str, upload_request_id: str) -> str:
    """`<setup_job_id>:<upload_request_id>` — компаунд-ключ."""
    return f"{setup_job_id}:{upload_request_id}"
