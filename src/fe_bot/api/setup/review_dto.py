"""SETUP-06 review API DTOs (T-S06-025)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# Requests
# ============================================================


class ReviewRAGCardRequest(BaseModel):
    """Approve или reject decision."""

    model_config = ConfigDict(extra="forbid")

    review_decision_id: str | None = None
    card_version: str | None = None
    decision: Literal["approve", "reject"]
    reason: str | None = None
    comment: str | None = Field(default=None, max_length=4000)


class EditRAGCardRequest(BaseModel):
    """Edit metadata/body."""

    model_config = ConfigDict(extra="forbid")

    expected_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    metadata_patch: dict[str, Any] | None = None
    body_markdown: str | None = None
    change_reason: str | None = Field(default=None, max_length=1000)


class RegenerateRAGCardReviewRequest(BaseModel):
    """Запрос регенерации через review flow."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=128)
    instruction: str | None = Field(default=None, max_length=4000)
    regenerate_request_id: str | None = None


class BulkReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")


class BulkReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bulk_review_id: str | None = None
    decision: Literal["approve"]  # MVP: только approve
    items: list[BulkReviewItem] = Field(..., min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=4000)


# ============================================================
# Responses
# ============================================================


class RAGCardReviewListItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    card_version: str
    title: str
    doc_type: str
    status: str
    confidence_level: str | None = None
    source_document_id: str | None = None
    source_section_id: str | None = None
    validation_errors_count: int = 0
    warnings_count: int = 0
    review_required_reason: str | None = None
    last_reviewed_by: str | None = None
    updated_at: datetime


class ReviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    by_status: dict[str, int] = Field(default_factory=dict)


class RAGCardReviewListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    items: list[RAGCardReviewListItemDTO]
    total: int
    page: int
    page_size: int
    summary: ReviewSummary


class ValidationItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ValidationReportDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critical_errors: list[ValidationItemDTO] = Field(default_factory=list)
    warnings: list[ValidationItemDTO] = Field(default_factory=list)


class ReviewPermissionsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_approve: bool
    can_reject: bool
    can_edit: bool
    can_regenerate: bool


class RAGCardReviewDetailsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    card_version: str
    title: str
    doc_type: str
    status: str
    confidence_level: str | None = None
    metadata: dict[str, Any]
    body_markdown: str
    source_trace: dict[str, Any]
    validation: ValidationReportDTO
    review_log_count: int
    permissions: ReviewPermissionsDTO


class ApproveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    card_version: str
    status: str
    review_decision_id: str
    reviewed_by: str
    reviewed_at: datetime


class RejectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    card_version: str
    status: str
    review_decision_id: str
    reason: str
    reviewed_by: str
    reviewed_at: datetime


class EditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    previous_version: str
    new_version: str
    status: str
    diff_available: bool
    edited_by: str
    edited_at: datetime


class RegenerateReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    card_version: str
    status: str
    regenerate_request_id: str
    generation_job_id: str | None = None
    message: str


class BulkReviewItemResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    status: str
    card_version: str | None = None
    error: str | None = None


class BulkReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bulk_review_id: str
    total: int
    approved: int
    errors: int
    results: list[BulkReviewItemResult]


class CardVersionItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    card_version: str
    parent_card_version: str | None = None
    status: str
    markdown_artifact_id: str
    body_hash: str
    created_by: str
    created_at: datetime
    change_reason: str | None = None
    is_current: bool


class RAGCardVersionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    versions: list[CardVersionItemDTO]


class CardDiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    from_version: str
    to_version: str
    body_changed: bool
    metadata_from: dict[str, Any]
    metadata_to: dict[str, Any]


class ReviewLogItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_log_id: str
    setup_job_id: str
    doc_id: str
    card_version: str
    event_type: str
    actor_id: str
    actor_role: str
    message: str
    before_status: str | None
    after_status: str | None
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    items: list[ReviewLogItemDTO]
