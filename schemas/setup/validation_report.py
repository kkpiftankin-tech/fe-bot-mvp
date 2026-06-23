"""ValidationReportDTO (DTO-32) — отчёт детерминированного валидатора.

Минимальная реализация под нужды T-S01-005. Полный контракт (с RAG-cards,
features, datasets, generation_spec target_type) дорабатывается в S5/S6.

Source of truth — docs/07-contracts/validation-report.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationTargetType(StrEnum):
    RAG_CARD = "rag_card"
    FEATURE = "feature"
    DATASET = "dataset"
    GENERATION_SPEC = "generation_spec"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    REPAIR_REQUIRED = "repair_required"


class ValidationIssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    """Одна проблема, найденная валидатором."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    field: str | None = None
    message: str = Field(..., min_length=1)
    severity: ValidationIssueSeverity = ValidationIssueSeverity.ERROR
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationCheck(BaseModel):
    """Описание одного выполненного check'а."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    passed: bool


class ValidationReport(BaseModel):
    """Отчёт валидации (DTO-32).

    SETUP-07 extension: добавлены optional поля для persisted reports:
    setup_job_id, card_version, policy_used, validation_run_id.
    """

    model_config = ConfigDict(extra="forbid")

    validation_report_id: str = Field(..., min_length=1)
    target_type: ValidationTargetType
    target_id: str = Field(..., min_length=1)
    status: ValidationStatus
    checks: list[ValidationCheck] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    repair_instruction: str | None = Field(None, max_length=4000)
    created_at: datetime
    validator_name: str = Field(..., min_length=1)
    # SETUP-07 (T-S07-002): persisted-report extension.
    setup_job_id: str | None = Field(default=None, max_length=128)
    card_version: str | None = Field(default=None, pattern=r"^\d+(\.\d+){0,2}$")
    policy_used: str | None = Field(default=None, max_length=64)
    validation_run_id: str | None = Field(default=None, max_length=128)

    @property
    def is_passing(self) -> bool:
        return self.status in {ValidationStatus.PASSED, ValidationStatus.WARNING}
