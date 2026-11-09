"""RAG Card Review events (SETUP-06 / T-S06-019).

8 domain-event'ов жизненного цикла review карточки. Публикуются через
EventBus как SetupProgressEvent с уникальными ``event_type`` строками
``rag_card.*`` / ``setup.review.*``.

Все модели frozen=True, extra="forbid".

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §16.2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Event type discriminators (SSE / логи / metrics).
EVENT_REVIEW_STARTED = "rag_card.review_started"
EVENT_APPROVED = "rag_card.approved"
EVENT_REJECTED = "rag_card.rejected"
EVENT_EDITED = "rag_card.edited"
EVENT_VERSION_CREATED = "rag_card.version_created"
EVENT_REGENERATE_REQUESTED = "rag_card.regenerate_requested"
EVENT_REVIEW_COMPLETED = "rag_card.review_completed"
EVENT_READINESS_CHANGED = "setup.review_readiness_changed"


class _BaseRAGCardReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    occurred_at: datetime


class RAGCardReviewStartedEvent(_BaseRAGCardReviewEvent):
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)


class RAGCardApprovedEvent(_BaseRAGCardReviewEvent):
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., min_length=1)
    review_decision_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    duration_ms: int = Field(..., ge=0)


class RAGCardRejectedEvent(_BaseRAGCardReviewEvent):
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., min_length=1)
    review_decision_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class RAGCardEditedEvent(_BaseRAGCardReviewEvent):
    doc_id: str = Field(..., min_length=1)
    previous_card_version: str = Field(..., min_length=1)
    new_card_version: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    metadata_changed: bool = False
    body_changed: bool = False


class RAGCardVersionCreatedEvent(_BaseRAGCardReviewEvent):
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., min_length=1)
    parent_card_version: str | None = None
    created_by: str = Field(..., min_length=1)
    change_reason: str | None = None


class RAGCardRegenerateRequestedEvent(_BaseRAGCardReviewEvent):
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., min_length=1)
    regenerate_request_id: str = Field(..., min_length=1)
    generation_job_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class RAGCardReviewCompletedEvent(_BaseRAGCardReviewEvent):
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., min_length=1)
    final_status: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)


class SetupReviewReadinessChangedEvent(_BaseRAGCardReviewEvent):
    total: int = Field(..., ge=0)
    approved: int = Field(..., ge=0)
    rejected: int = Field(..., ge=0)
    blocking: int = Field(..., ge=0)
    ready_for_next_step: bool


RAGCardReviewEvent = (
    RAGCardReviewStartedEvent
    | RAGCardApprovedEvent
    | RAGCardRejectedEvent
    | RAGCardEditedEvent
    | RAGCardVersionCreatedEvent
    | RAGCardRegenerateRequestedEvent
    | RAGCardReviewCompletedEvent
    | SetupReviewReadinessChangedEvent
)


def event_type_of(event: _BaseRAGCardReviewEvent) -> str:
    mapping: dict[type, str] = {
        RAGCardReviewStartedEvent: EVENT_REVIEW_STARTED,
        RAGCardApprovedEvent: EVENT_APPROVED,
        RAGCardRejectedEvent: EVENT_REJECTED,
        RAGCardEditedEvent: EVENT_EDITED,
        RAGCardVersionCreatedEvent: EVENT_VERSION_CREATED,
        RAGCardRegenerateRequestedEvent: EVENT_REGENERATE_REQUESTED,
        RAGCardReviewCompletedEvent: EVENT_REVIEW_COMPLETED,
        SetupReviewReadinessChangedEvent: EVENT_READINESS_CHANGED,
    }
    return mapping[type(event)]


def event_payload(event: _BaseRAGCardReviewEvent) -> dict[str, Any]:
    return event.model_dump(mode="json")
