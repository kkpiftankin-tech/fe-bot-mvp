"""ReviewLogRepository (SETUP-06 / T-S06-008).

Append-only журнал review-действий. Все записи иммутабельны
(ReviewLogDTO frozen=True), удаление не поддерживается в API.

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.review_log import ReviewLogDTO


class ReviewLogRepository(Protocol):
    def append(self, entry: ReviewLogDTO) -> None: ...

    def list_for_card(
        self,
        doc_id: str,
        *,
        limit: int | None = None,
    ) -> list[ReviewLogDTO]: ...

    def list_for_setup_job(
        self,
        setup_job_id: str,
        *,
        limit: int | None = None,
    ) -> list[ReviewLogDTO]: ...

    def count_for_card(self, doc_id: str) -> int: ...


class InMemoryReviewLogRepository:
    """Append-only chronological log."""

    def __init__(self) -> None:
        self._entries: list[ReviewLogDTO] = []
        self._lock = threading.Lock()

    def append(self, entry: ReviewLogDTO) -> None:
        with self._lock:
            self._entries.append(entry)

    def list_for_card(
        self,
        doc_id: str,
        *,
        limit: int | None = None,
    ) -> list[ReviewLogDTO]:
        with self._lock:
            filtered = [e for e in self._entries if e.doc_id == doc_id]
        # Chronological order сохраняется (append-order).
        if limit is not None:
            return filtered[-limit:]
        return filtered

    def list_for_setup_job(
        self,
        setup_job_id: str,
        *,
        limit: int | None = None,
    ) -> list[ReviewLogDTO]:
        with self._lock:
            filtered = [e for e in self._entries if e.setup_job_id == setup_job_id]
        if limit is not None:
            return filtered[-limit:]
        return filtered

    def count_for_card(self, doc_id: str) -> int:
        with self._lock:
            return sum(1 for e in self._entries if e.doc_id == doc_id)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    # ----- Snapshot -----

    def snapshot(self) -> list[object]:
        with self._lock:
            return [e.model_dump(mode="json") for e in self._entries]

    def restore(self, data: list[object]) -> None:
        with self._lock:
            self._entries = [ReviewLogDTO.model_validate(raw) for raw in data]
