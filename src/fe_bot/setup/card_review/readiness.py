"""ReviewReadinessCalculator (SETUP-06 / T-S06-017).

Подсчитывает агрегат review-статусов карточек setup_job и определяет,
готов ли job к переходу на следующий этап (SETUP-07).

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §7.1 (шаг 14).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from schemas.rag.rag_card import CardStatus, RAGCard


@dataclass(frozen=True)
class ReadinessSummary:
    """Агрегат состояния review для setup_job."""

    setup_job_id: str
    total: int
    approved: int
    rejected: int
    review_required: int
    validation_failed: int
    metadata_incomplete: int
    low_confidence: int
    edited: int
    regenerate_requested: int
    ready_for_next_step: bool


# Статусы, блокирующие переход к SETUP-07.
_BLOCKING_STATUSES: frozenset[CardStatus] = frozenset(
    {
        CardStatus.REVIEW_REQUIRED,
        CardStatus.VALIDATION_FAILED,
        CardStatus.METADATA_INCOMPLETE,
        CardStatus.LOW_CONFIDENCE,
        CardStatus.EDITING,
        CardStatus.GENERATED,  # generated всё ещё ждёт review
    }
)


class _CardRegistryLike(Protocol):
    def list_for_setup_job(self, setup_job_id: str) -> list[RAGCard]: ...


class ReviewReadinessCalculator:
    """Считает агрегат статусов и возвращает ReadinessSummary."""

    def __init__(self, *, card_registry: _CardRegistryLike) -> None:
        self._registry = card_registry

    def calculate(self, setup_job_id: str) -> ReadinessSummary:
        cards = self._registry.list_for_setup_job(setup_job_id)

        counters: dict[CardStatus, int] = {}
        for card in cards:
            counters[card.status] = counters.get(card.status, 0) + 1

        blocking = sum(counters.get(s, 0) for s in _BLOCKING_STATUSES)
        total = len(cards)

        return ReadinessSummary(
            setup_job_id=setup_job_id,
            total=total,
            approved=counters.get(CardStatus.APPROVED, 0)
            + counters.get(CardStatus.READY_FOR_METADATA_VALIDATION, 0),
            rejected=counters.get(CardStatus.REJECTED, 0),
            review_required=counters.get(CardStatus.REVIEW_REQUIRED, 0),
            validation_failed=counters.get(CardStatus.VALIDATION_FAILED, 0),
            metadata_incomplete=counters.get(CardStatus.METADATA_INCOMPLETE, 0),
            low_confidence=counters.get(CardStatus.LOW_CONFIDENCE, 0),
            edited=counters.get(CardStatus.EDITED, 0),
            regenerate_requested=counters.get(CardStatus.REGENERATE_REQUESTED, 0),
            ready_for_next_step=(total > 0 and blocking == 0),
        )
