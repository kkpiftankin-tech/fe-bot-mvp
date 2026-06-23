"""SETUP-07 validation events (T-S07-006)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


EVENT_RUN_STARTED = "validation.run_started"
EVENT_RUN_COMPLETED = "validation.run_completed"
EVENT_REPORT_CREATED = "validation.report_created"


class _BaseValidationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    occurred_at: datetime


class ValidationRunStartedEvent(_BaseValidationEvent):
    validation_run_id: str = Field(..., min_length=1)
    triggered_by: str = Field(..., min_length=1)
    policy: str = Field(..., min_length=1)
    total: int = Field(..., ge=0)


class ValidationRunCompletedEvent(_BaseValidationEvent):
    validation_run_id: str = Field(..., min_length=1)
    total: int = Field(..., ge=0)
    passed: int = Field(..., ge=0)
    warnings: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    review_required: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)


class ValidationReportCreatedEvent(_BaseValidationEvent):
    validation_report_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    card_version: str | None = None
    status: str = Field(..., min_length=1)
    errors_count: int = Field(default=0, ge=0)
    warnings_count: int = Field(default=0, ge=0)


ValidationEvent = (
    ValidationRunStartedEvent
    | ValidationRunCompletedEvent
    | ValidationReportCreatedEvent
)


def event_type_of(event: _BaseValidationEvent) -> str:
    mapping: dict[type, str] = {
        ValidationRunStartedEvent: EVENT_RUN_STARTED,
        ValidationRunCompletedEvent: EVENT_RUN_COMPLETED,
        ValidationReportCreatedEvent: EVENT_REPORT_CREATED,
    }
    return mapping[type(event)]


def event_payload(event: _BaseValidationEvent) -> dict[str, Any]:
    return event.model_dump(mode="json")
