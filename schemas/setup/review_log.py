"""ReviewLogDTO (SETUP-06 / T-S06-002).

Append-only журнал review-действий. Каждое изменение статуса/версии/lock'а
производит запись.

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §11.2.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewLogEventType(StrEnum):
    """Типы событий review log (см. spec §14.2)."""

    REVIEW_STARTED = "review_started"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    REGENERATE_REQUESTED = "regenerate_requested"
    VERSION_CREATED = "version_created"
    REVIEW_COMPLETED = "review_completed"
    EDIT_LOCK_ACQUIRED = "edit_lock_acquired"
    EDIT_LOCK_RELEASED = "edit_lock_released"


class ReviewLogDTO(BaseModel):
    """Иммутабельная запись журнала review.

    Storage: PostgreSQL `rag_card_review_logs` (план); MVP — in-memory append-only.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_log_id: str = Field(..., min_length=1, max_length=128)
    setup_job_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    event_type: ReviewLogEventType
    actor_id: str = Field(..., min_length=1, max_length=128)
    actor_role: str = Field(..., min_length=1, max_length=64)
    message: str = Field(..., min_length=1, max_length=4000)
    before_status: str | None = None
    after_status: str | None = None
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
