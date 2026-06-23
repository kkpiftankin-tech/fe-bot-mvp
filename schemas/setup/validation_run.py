"""ValidationRunDTO (SETUP-07 / T-S07-001).

Агрегат одного прогона валидации по setup_job: общая статистика, статус,
время выполнения, кто инициировал.

Source of truth — docs/02-system/features/SETUP-07-metadata-validation.md §11.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValidationRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationRunDTO(BaseModel):
    """Иммутабельная запись о прогоне валидации.

    Storage: PostgreSQL `validation_runs` (план); MVP — in-memory.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    validation_run_id: str = Field(..., min_length=1, max_length=128)
    setup_job_id: str = Field(..., min_length=1)
    status: ValidationRunStatus
    triggered_by: str = Field(..., min_length=1, max_length=128)
    policy: str = Field(..., min_length=1, max_length=64)
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    review_required: int = Field(default=0, ge=0)
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    error_message: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check_completed_has_finished(self) -> ValidationRunDTO:
        if (
            self.status == ValidationRunStatus.COMPLETED
            and self.finished_at is None
        ):
            raise ValueError("completed run requires finished_at")
        return self
