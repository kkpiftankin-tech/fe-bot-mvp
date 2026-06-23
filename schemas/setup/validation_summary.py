"""ValidationSummaryDTO (SETUP-07 / T-S07-002).

Агрегат счётчиков валидации для UI summary card.

Source of truth — docs/02-system/features/SETUP-07-metadata-validation.md §9.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ValidationSummaryDTO(BaseModel):
    """Счётчики reports по setup_job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    setup_job_id: str = Field(..., min_length=1)
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    review_required: int = Field(default=0, ge=0)
    by_code: dict[str, int] = Field(default_factory=dict)
    last_run_id: str | None = None
