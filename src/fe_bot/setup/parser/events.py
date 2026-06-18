"""ParseJob events (SETUP-04 / T-S04-019).

10 doman-event'ов жизненного цикла ParseJob — публикуются через
существующий EventBus как SetupProgressEvent с уникальными
``event_type`` строками вида ``parse.job.*`` / ``parse.document.*`` /
``parse.section.*``.

В отличие от SetupProgressEvent (DTO-49), эти модели — frozen, extra=forbid,
служат типизированной payload-частью для in-process наблюдателей.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Event type discriminators (для SSE и логирования).
EVENT_PARSE_JOB_CREATED = "parse.job.created"
EVENT_PARSE_JOB_STARTED = "parse.job.started"
EVENT_PARSE_JOB_COMPLETED = "parse.job.completed"
EVENT_PARSE_JOB_FAILED = "parse.job.failed"
EVENT_PARSE_JOB_PARTIAL_SUCCESS = "parse.job.partial_success"
EVENT_PARSE_DOCUMENT_STARTED = "parse.document.started"
EVENT_PARSE_DOCUMENT_COMPLETED = "parse.document.completed"
EVENT_PARSE_DOCUMENT_FAILED = "parse.document.failed"
EVENT_PARSED_SECTIONS_CREATED = "parse.sections.created"
EVENT_SECTION_LOW_CONFIDENCE = "parse.section.low_confidence"


class _BaseParseEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    parse_job_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    occurred_at: datetime


class ParseJobCreatedEvent(_BaseParseEvent):
    total_documents: int = Field(..., ge=0)
    requested_by: str = Field(..., min_length=1)


class ParseJobStartedEvent(_BaseParseEvent):
    total_documents: int = Field(..., ge=0)


class ParseJobCompletedEvent(_BaseParseEvent):
    total_documents: int = Field(..., ge=0)
    succeeded: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    skipped: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)


class ParseJobFailedEvent(_BaseParseEvent):
    error_code: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class ParseJobPartialSuccessEvent(_BaseParseEvent):
    succeeded: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    skipped: int = Field(..., ge=0)


class ParseDocumentStartedEvent(_BaseParseEvent):
    source_document_id: str = Field(..., min_length=1)
    strategy: str = Field(..., min_length=1)


class ParseDocumentCompletedEvent(_BaseParseEvent):
    source_document_id: str = Field(..., min_length=1)
    sections_count: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)


class ParseDocumentFailedEvent(_BaseParseEvent):
    source_document_id: str = Field(..., min_length=1)
    error_code: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class ParsedSectionsCreatedEvent(_BaseParseEvent):
    source_document_id: str = Field(..., min_length=1)
    section_ids: list[str] = Field(default_factory=list)
    sections_count: int = Field(..., ge=0)


class SectionClassificationLowConfidenceEvent(_BaseParseEvent):
    section_id: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    candidate_type: str = Field(..., min_length=1)


ParseEvent = (
    ParseJobCreatedEvent
    | ParseJobStartedEvent
    | ParseJobCompletedEvent
    | ParseJobFailedEvent
    | ParseJobPartialSuccessEvent
    | ParseDocumentStartedEvent
    | ParseDocumentCompletedEvent
    | ParseDocumentFailedEvent
    | ParsedSectionsCreatedEvent
    | SectionClassificationLowConfidenceEvent
)


def event_type_of(event: _BaseParseEvent) -> str:
    """Возвращает строковый discriminator для конкретного event-класса."""
    mapping: dict[type, str] = {
        ParseJobCreatedEvent: EVENT_PARSE_JOB_CREATED,
        ParseJobStartedEvent: EVENT_PARSE_JOB_STARTED,
        ParseJobCompletedEvent: EVENT_PARSE_JOB_COMPLETED,
        ParseJobFailedEvent: EVENT_PARSE_JOB_FAILED,
        ParseJobPartialSuccessEvent: EVENT_PARSE_JOB_PARTIAL_SUCCESS,
        ParseDocumentStartedEvent: EVENT_PARSE_DOCUMENT_STARTED,
        ParseDocumentCompletedEvent: EVENT_PARSE_DOCUMENT_COMPLETED,
        ParseDocumentFailedEvent: EVENT_PARSE_DOCUMENT_FAILED,
        ParsedSectionsCreatedEvent: EVENT_PARSED_SECTIONS_CREATED,
        SectionClassificationLowConfidenceEvent: EVENT_SECTION_LOW_CONFIDENCE,
    }
    return mapping[type(event)]


def event_payload(event: _BaseParseEvent) -> dict[str, Any]:
    """Сериализует event для metrics-канала SetupProgressEvent."""
    payload = event.model_dump(mode="json")
    # event_id / parse_job_id уже есть в SetupProgressEvent.metrics — оставляем
    # для self-contained payload'а, верхний уровень их продублирует.
    return payload
