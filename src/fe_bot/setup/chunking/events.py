"""SETUP-08 chunking events (T-S08-003)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


EVENT_RUN_STARTED = "chunking.run_started"
EVENT_RUN_COMPLETED = "chunking.run_completed"


class _BaseChunkingEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    occurred_at: datetime


class ChunkingRunStartedEvent(_BaseChunkingEvent):
    chunking_run_id: str = Field(..., min_length=1)
    triggered_by: str = Field(..., min_length=1)
    total_cards: int = Field(..., ge=0)


class ChunkingRunCompletedEvent(_BaseChunkingEvent):
    chunking_run_id: str = Field(..., min_length=1)
    manifest_id: str = Field(..., min_length=1)
    total_cards: int = Field(..., ge=0)
    chunks_created: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)


ChunkingEvent = ChunkingRunStartedEvent | ChunkingRunCompletedEvent


def event_type_of(event: _BaseChunkingEvent) -> str:
    mapping: dict[type, str] = {
        ChunkingRunStartedEvent: EVENT_RUN_STARTED,
        ChunkingRunCompletedEvent: EVENT_RUN_COMPLETED,
    }
    return mapping[type(event)]


def event_payload(event: _BaseChunkingEvent) -> dict[str, Any]:
    return event.model_dump(mode="json")
