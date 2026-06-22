"""RAG Card Generation events (SETUP-05 / T-S05-022).

8 domain-event'ов жизненного цикла RAGCardGenerationJob. Публикуются через
существующий EventBus как SetupProgressEvent с уникальными ``event_type``
строками вида ``rag_card_generation.*`` / ``rag_card.*``.

Все модели frozen=True, extra="forbid" — payload для in-process наблюдателей.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Event type discriminators (SSE / логи / metrics).
EVENT_JOB_CREATED = "rag_card_generation.job.created"
EVENT_JOB_STARTED = "rag_card_generation.job.started"
EVENT_JOB_COMPLETED = "rag_card_generation.job.completed"
EVENT_JOB_FAILED = "rag_card_generation.job.failed"
EVENT_JOB_PARTIAL_SUCCESS = "rag_card_generation.job.partial_success"
EVENT_CARD_GENERATED = "rag_card.generated"
EVENT_CARD_REVIEW_REQUIRED = "rag_card.review_required"
EVENT_CARD_GENERATION_FAILED = "rag_card.generation_failed"


class _BaseRAGCardGenerationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    generation_job_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    occurred_at: datetime


class RAGCardGenerationJobCreatedEvent(_BaseRAGCardGenerationEvent):
    total_sections: int = Field(..., ge=0)
    requested_by: str = Field(..., min_length=1)


class RAGCardGenerationJobStartedEvent(_BaseRAGCardGenerationEvent):
    total_sections: int = Field(..., ge=0)


class RAGCardGenerationJobCompletedEvent(_BaseRAGCardGenerationEvent):
    total_sections: int = Field(..., ge=0)
    generated_cards: int = Field(..., ge=0)
    failed_sections: int = Field(..., ge=0)
    review_required_cards: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)


class RAGCardGenerationJobFailedEvent(_BaseRAGCardGenerationEvent):
    error_code: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class RAGCardGenerationJobPartialSuccessEvent(_BaseRAGCardGenerationEvent):
    generated_cards: int = Field(..., ge=0)
    failed_sections: int = Field(..., ge=0)
    review_required_cards: int = Field(..., ge=0)


class RAGCardGeneratedEvent(_BaseRAGCardGenerationEvent):
    section_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    doc_type: str = Field(..., min_length=1)
    card_version: str = Field(..., min_length=1)
    confidence_level: str = Field(..., min_length=1)


class RAGCardReviewRequiredEvent(_BaseRAGCardGenerationEvent):
    section_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    reasons: list[str] = Field(default_factory=list)


class RAGCardGenerationFailedEvent(_BaseRAGCardGenerationEvent):
    section_id: str = Field(..., min_length=1)
    error_code: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


RAGCardGenerationEvent = (
    RAGCardGenerationJobCreatedEvent
    | RAGCardGenerationJobStartedEvent
    | RAGCardGenerationJobCompletedEvent
    | RAGCardGenerationJobFailedEvent
    | RAGCardGenerationJobPartialSuccessEvent
    | RAGCardGeneratedEvent
    | RAGCardReviewRequiredEvent
    | RAGCardGenerationFailedEvent
)


def event_type_of(event: _BaseRAGCardGenerationEvent) -> str:
    """Возвращает строковый discriminator для конкретного event-класса."""
    mapping: dict[type, str] = {
        RAGCardGenerationJobCreatedEvent: EVENT_JOB_CREATED,
        RAGCardGenerationJobStartedEvent: EVENT_JOB_STARTED,
        RAGCardGenerationJobCompletedEvent: EVENT_JOB_COMPLETED,
        RAGCardGenerationJobFailedEvent: EVENT_JOB_FAILED,
        RAGCardGenerationJobPartialSuccessEvent: EVENT_JOB_PARTIAL_SUCCESS,
        RAGCardGeneratedEvent: EVENT_CARD_GENERATED,
        RAGCardReviewRequiredEvent: EVENT_CARD_REVIEW_REQUIRED,
        RAGCardGenerationFailedEvent: EVENT_CARD_GENERATION_FAILED,
    }
    return mapping[type(event)]


def event_payload(event: _BaseRAGCardGenerationEvent) -> dict[str, Any]:
    """Сериализует event для metrics-канала SetupProgressEvent."""
    return event.model_dump(mode="json")
