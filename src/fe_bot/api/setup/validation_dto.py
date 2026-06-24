"""SETUP-07 validation API DTOs (T-S07-012)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Requests
# ============================================================


class RunValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: str | None = Field(default=None, max_length=64)


class RefreshValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_request_id: str | None = None


# ============================================================
# Responses
# ============================================================


class ValidationIssueItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    field: str | None = None
    message: str
    severity: str
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationCheckItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool


class ValidationReportItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_report_id: str
    setup_job_id: str | None = None
    doc_id: str
    card_version: str | None = None
    status: str
    errors: list[ValidationIssueItemDTO] = Field(default_factory=list)
    warnings: list[ValidationIssueItemDTO] = Field(default_factory=list)
    checks: list[ValidationCheckItemDTO] = Field(default_factory=list)
    policy_used: str | None = None
    validation_run_id: str | None = None
    validator_name: str
    created_at: datetime


class ValidationReportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    items: list[ValidationReportItemDTO]
    total: int


class ValidationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_run_id: str
    setup_job_id: str
    status: str
    triggered_by: str
    policy: str
    total: int
    passed: int
    warnings: int
    failed: int
    review_required: int
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None


class ValidationSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    total: int
    passed: int
    warnings: int
    failed: int
    review_required: int
    by_code: dict[str, int] = Field(default_factory=dict)
    last_run_id: str | None = None
