"""ReviewDecisionDTO (SETUP-06 / T-S06-001).

Решение пользователя по RAG-карточке: approve/reject/edit/regenerate.

Идемпотентен по ``review_decision_id``: повторный append с тем же id —
возврат существующей записи.

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §15.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewDecision(StrEnum):
    """Решение review (см. spec §3)."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    REGENERATE = "regenerate"
    SAVE_DRAFT = "save_draft"
    SUBMIT_EDIT = "submit_edit"
    REQUEST_CHANGES = "request_changes"
    DEFER = "defer"


class RejectReason(StrEnum):
    """Стандартные причины отклонения карточки (см. spec §7.2 A3)."""

    DUPLICATE = "duplicate"
    WRONG_DOC_TYPE = "wrong_doc_type"
    INCORRECT_CONTENT = "incorrect_content"
    IRRELEVANT = "irrelevant"
    HALLUCINATION = "hallucination"
    SOURCE_MISMATCH = "source_mismatch"
    OTHER = "other"


class RegenerateReason(StrEnum):
    """Причины запроса регенерации."""

    LOW_QUALITY = "low_quality"
    WRONG_DOC_TYPE = "wrong_doc_type"
    INCORRECT_METADATA = "incorrect_metadata"
    HALLUCINATION = "hallucination"
    INCOMPLETE = "incomplete"
    OTHER = "other"


class ReviewDecisionDTO(BaseModel):
    """Иммутабельная запись review-решения.

    Идемпотентность через ``review_decision_id`` (UUID или client-supplied).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_decision_id: str = Field(..., min_length=1, max_length=128)
    setup_job_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    decision: ReviewDecision
    reason: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=4000)
    reviewer_id: str = Field(..., min_length=1, max_length=128)
    reviewer_role: str = Field(..., min_length=1, max_length=64)
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_reason_for_decision(self) -> ReviewDecisionDTO:
        """Reject и regenerate требуют reason (см. AC-23, AC-35)."""
        if self.decision == ReviewDecision.REJECT and not self.reason:
            raise ValueError(
                "reject decision requires reason (AC-23: REJECT_REASON_REQUIRED)"
            )
        if self.decision == ReviewDecision.REGENERATE and not self.reason:
            raise ValueError(
                "regenerate decision requires reason "
                "(AC-35: REGENERATE_REASON_REQUIRED)"
            )
        return self
