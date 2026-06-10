"""RAGSetupJobDTO (DTO-07) — job настройки RAG-базы.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-07.
Машина состояний — docs/02-system/features/SETUP-01-setup-wizard.md §3.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SetupJobStatus(StrEnum):
    """15 статусов setup job (см. SETUP-01 §3)."""

    DRAFT = "draft"
    FILES_UPLOADED = "files_uploaded"
    PARSING = "parsing"
    SECTIONS_EXTRACTED = "sections_extracted"
    RAG_CARDS_GENERATING = "rag_cards_generating"
    METADATA_VALIDATING = "metadata_validating"
    REVIEW_REQUIRED = "review_required"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    RETRIEVAL_TESTING = "retrieval_testing"
    PUBLISHING = "publishing"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Машина переходов. Любой ключ может перейти в любое значение из множества.
# `failed` допускает rerun-from-step (см. SETUP-01 §7.2 A4).
_ALLOWED_TRANSITIONS: dict[SetupJobStatus, frozenset[SetupJobStatus]] = {
    SetupJobStatus.DRAFT: frozenset(
        {SetupJobStatus.FILES_UPLOADED, SetupJobStatus.CANCELLED, SetupJobStatus.FAILED}
    ),
    SetupJobStatus.FILES_UPLOADED: frozenset(
        {SetupJobStatus.PARSING, SetupJobStatus.CANCELLED, SetupJobStatus.FAILED}
    ),
    SetupJobStatus.PARSING: frozenset(
        {
            SetupJobStatus.SECTIONS_EXTRACTED,
            SetupJobStatus.FAILED,
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.SECTIONS_EXTRACTED: frozenset(
        {
            SetupJobStatus.RAG_CARDS_GENERATING,
            SetupJobStatus.FAILED,
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.RAG_CARDS_GENERATING: frozenset(
        {
            SetupJobStatus.METADATA_VALIDATING,
            SetupJobStatus.FAILED,
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.METADATA_VALIDATING: frozenset(
        {
            SetupJobStatus.REVIEW_REQUIRED,
            SetupJobStatus.CHUNKING,
            SetupJobStatus.FAILED,
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.REVIEW_REQUIRED: frozenset(
        {
            SetupJobStatus.CHUNKING,
            SetupJobStatus.RAG_CARDS_GENERATING,  # regenerate after reject
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.CHUNKING: frozenset(
        {SetupJobStatus.EMBEDDING, SetupJobStatus.FAILED, SetupJobStatus.CANCELLED}
    ),
    SetupJobStatus.EMBEDDING: frozenset(
        {SetupJobStatus.INDEXING, SetupJobStatus.FAILED, SetupJobStatus.CANCELLED}
    ),
    SetupJobStatus.INDEXING: frozenset(
        {
            SetupJobStatus.RETRIEVAL_TESTING,
            SetupJobStatus.FAILED,
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.RETRIEVAL_TESTING: frozenset(
        {
            SetupJobStatus.PUBLISHING,
            SetupJobStatus.REVIEW_REQUIRED,  # частичный pass — admin решает
            SetupJobStatus.FAILED,
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.PUBLISHING: frozenset(
        {SetupJobStatus.READY, SetupJobStatus.FAILED, SetupJobStatus.CANCELLED}
    ),
    SetupJobStatus.READY: frozenset({SetupJobStatus.CANCELLED}),  # terminal-кроме отмены admin
    SetupJobStatus.FAILED: frozenset(
        {
            SetupJobStatus.PARSING,
            SetupJobStatus.RAG_CARDS_GENERATING,
            SetupJobStatus.CHUNKING,
            SetupJobStatus.EMBEDDING,
            SetupJobStatus.INDEXING,
            SetupJobStatus.RETRIEVAL_TESTING,
            SetupJobStatus.CANCELLED,
        }
    ),
    SetupJobStatus.CANCELLED: frozenset(),  # terminal
}


class InvalidTransitionError(ValueError):
    """Поднимается при попытке невалидного перехода статусов."""

    def __init__(self, from_status: SetupJobStatus, to_status: SetupJobStatus) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid setup job status transition: {from_status.value} → {to_status.value}"
        )


class RAGSetupJob(BaseModel):
    """Job настройки RAG-базы. Соответствует DTO-07."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    setup_job_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    project_name: str = Field(..., min_length=3, max_length=128)
    status: SetupJobStatus = SetupJobStatus.DRAFT
    current_step: str | None = None
    progress_percent: float = Field(0.0, ge=0.0, le=100.0)
    source_document_ids: list[str] = Field(default_factory=list)
    knowledge_base_version: str | None = None
    error_count: int = Field(0, ge=0)
    warning_count: int = Field(0, ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("project_name")
    @classmethod
    def _strip_project_name(cls, v: str) -> str:
        return v.strip()

    def can_transition_to(self, new_status: SetupJobStatus) -> bool:
        """True если переход current.status → new_status разрешён."""
        return new_status in _ALLOWED_TRANSITIONS.get(self.status, frozenset())

    def transition_to(self, new_status: SetupJobStatus) -> None:
        """Меняет status, валидируя переход.

        Raises:
            InvalidTransitionError: если переход не разрешён.
        """
        if not self.can_transition_to(new_status):
            raise InvalidTransitionError(self.status, new_status)
        self.status = new_status

    @property
    def is_terminal(self) -> bool:
        """True если из статуса нельзя никуда уйти (кроме `ready → cancelled`)."""
        return self.status in {SetupJobStatus.CANCELLED} or (
            self.status == SetupJobStatus.READY
        )
