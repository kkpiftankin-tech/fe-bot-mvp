"""ReviewDecisionRepository (SETUP-06 / T-S06-007).

Хранит решения review (approve/reject/edit/regenerate). Идемпотентен по
``review_decision_id``: повторный append с тем же id — no-op + возврат
существующего.

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.review_decision import ReviewDecisionDTO


class ReviewDecisionNotFoundError(KeyError):
    def __init__(self, review_decision_id: str) -> None:
        self.review_decision_id = review_decision_id
        super().__init__(f"ReviewDecision {review_decision_id!r} not found")


class ReviewDecisionRepository(Protocol):
    def add(self, decision: ReviewDecisionDTO) -> ReviewDecisionDTO: ...

    def get(self, review_decision_id: str) -> ReviewDecisionDTO: ...

    def exists(self, review_decision_id: str) -> bool: ...

    def list_for_card(self, doc_id: str) -> list[ReviewDecisionDTO]: ...

    def list_for_setup_job(self, setup_job_id: str) -> list[ReviewDecisionDTO]: ...

    def list_for_reviewer(self, reviewer_id: str) -> list[ReviewDecisionDTO]: ...


class InMemoryReviewDecisionRepository:
    """In-memory + thread-safe + idempotent."""

    def __init__(self) -> None:
        self._by_id: dict[str, ReviewDecisionDTO] = {}
        self._lock = threading.Lock()

    def add(self, decision: ReviewDecisionDTO) -> ReviewDecisionDTO:
        """Идемпотентное добавление.

        Повторный вызов с тем же ``review_decision_id`` возвращает
        существующую запись без изменения.
        """
        with self._lock:
            existing = self._by_id.get(decision.review_decision_id)
            if existing is not None:
                return existing
            self._by_id[decision.review_decision_id] = decision
            return decision

    def get(self, review_decision_id: str) -> ReviewDecisionDTO:
        with self._lock:
            try:
                return self._by_id[review_decision_id]
            except KeyError as exc:
                raise ReviewDecisionNotFoundError(review_decision_id) from exc

    def exists(self, review_decision_id: str) -> bool:
        with self._lock:
            return review_decision_id in self._by_id

    def list_for_card(self, doc_id: str) -> list[ReviewDecisionDTO]:
        with self._lock:
            return [d for d in self._by_id.values() if d.doc_id == doc_id]

    def list_for_setup_job(self, setup_job_id: str) -> list[ReviewDecisionDTO]:
        with self._lock:
            return [d for d in self._by_id.values() if d.setup_job_id == setup_job_id]

    def list_for_reviewer(self, reviewer_id: str) -> list[ReviewDecisionDTO]:
        with self._lock:
            return [d for d in self._by_id.values() if d.reviewer_id == reviewer_id]

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()

    # ----- Snapshot -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {rid: d.model_dump(mode="json") for rid, d in self._by_id.items()}

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._by_id.clear()
            for rid, raw in data.items():
                self._by_id[rid] = ReviewDecisionDTO.model_validate(raw)
