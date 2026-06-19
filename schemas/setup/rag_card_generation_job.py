"""RAGCardGenerationJob DTO (SETUP-05) — lifecycle-сущность задания генерации RAG-карточек.

Аналог ParseJob из SETUP-04: один RAGSetupJob → 1..N RAGCardGenerationJob
(regenerate создаёт новый job). Содержит state machine, агрегированные счётчики
и config генерации (model, prompt_template_version, ontology_version,
confidence_threshold).

Source of truth — docs/02-system/features/SETUP-05-rag-cards-generation.md §15.2,
docs/03-architecture/services/data-transfer-objects.md DTO-59.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RAGCardGenerationJobStatus(StrEnum):
    """Статусы lifecycle RAGCardGenerationJob.

    Допустимые переходы — в RAG_CARD_JOB_ALLOWED_TRANSITIONS.
    """

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RAGCardGenerationErrorCode(StrEnum):
    """Коды ошибок генерации RAG-карточек (SETUP-05 §18.1, §18.2)."""

    SETUP_JOB_NOT_FOUND = "SETUP_JOB_NOT_FOUND"
    NO_SECTIONS_READY_FOR_CARD_GENERATION = "NO_SECTIONS_READY_FOR_CARD_GENERATION"
    SECTION_NOT_FOUND = "SECTION_NOT_FOUND"
    SECTION_NOT_READY = "SECTION_NOT_READY"
    INVALID_GENERATION_MODE = "INVALID_GENERATION_MODE"
    ONTOLOGY_VERSION_NOT_FOUND = "ONTOLOGY_VERSION_NOT_FOUND"
    METADATA_SCHEMA_NOT_FOUND = "METADATA_SCHEMA_NOT_FOUND"
    PROMPT_TEMPLATE_NOT_FOUND = "PROMPT_TEMPLATE_NOT_FOUND"
    RAG_CARD_GENERATION_ALREADY_RUNNING = "RAG_CARD_GENERATION_ALREADY_RUNNING"
    LLM_GATEWAY_UNAVAILABLE = "LLM_GATEWAY_UNAVAILABLE"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    INVALID_LLM_OUTPUT = "INVALID_LLM_OUTPUT"
    INVALID_DOC_TYPE = "INVALID_DOC_TYPE"
    DOC_ID_CONFLICT = "DOC_ID_CONFLICT"
    CARD_BODY_EMPTY = "CARD_BODY_EMPTY"


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

#: Допустимые переходы RAGCardGenerationJobStatus.
RAG_CARD_JOB_ALLOWED_TRANSITIONS: dict[
    RAGCardGenerationJobStatus, frozenset[RAGCardGenerationJobStatus]
] = {
    RAGCardGenerationJobStatus.CREATED: frozenset(
        {
            RAGCardGenerationJobStatus.QUEUED,
            RAGCardGenerationJobStatus.CANCELLED,
        }
    ),
    RAGCardGenerationJobStatus.QUEUED: frozenset(
        {
            RAGCardGenerationJobStatus.RUNNING,
            RAGCardGenerationJobStatus.CANCELLED,
            RAGCardGenerationJobStatus.FAILED,
        }
    ),
    RAGCardGenerationJobStatus.RUNNING: frozenset(
        {
            RAGCardGenerationJobStatus.COMPLETED,
            RAGCardGenerationJobStatus.PARTIAL_SUCCESS,
            RAGCardGenerationJobStatus.FAILED,
            RAGCardGenerationJobStatus.CANCELLED,
        }
    ),
    # Terminal:
    RAGCardGenerationJobStatus.PARTIAL_SUCCESS: frozenset(),
    RAGCardGenerationJobStatus.COMPLETED: frozenset(),
    RAGCardGenerationJobStatus.FAILED: frozenset(),
    RAGCardGenerationJobStatus.CANCELLED: frozenset(),
}


class InvalidRAGCardJobTransitionError(ValueError):
    """Недопустимый переход RAGCardGenerationJob.status."""

    def __init__(
        self,
        generation_job_id: str,
        from_status: RAGCardGenerationJobStatus,
        to_status: RAGCardGenerationJobStatus,
    ) -> None:
        self.generation_job_id = generation_job_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid RAGCardGenerationJob transition for {generation_job_id}: "
            f"{from_status.value} → {to_status.value}"
        )


# ---------------------------------------------------------------------------
# HTTP status mapping
# ---------------------------------------------------------------------------


def http_status_for(code: RAGCardGenerationErrorCode) -> int:
    """HTTP-статус для RAGCardGenerationErrorCode.

    Семантика:
      400 — клиентская ошибка (валидация запроса, нет секций).
      403 — нет прав.
      404 — ресурс не найден.
      409 — конфликт состояния (уже запущен, секция не готова).
      422 — невозможно обработать (LLM output не валиден, body пуст).
      500 — внутренняя ошибка.
      504 — таймаут LLM.
    """
    _MAP: dict[RAGCardGenerationErrorCode, int] = {
        RAGCardGenerationErrorCode.SETUP_JOB_NOT_FOUND: 404,
        RAGCardGenerationErrorCode.NO_SECTIONS_READY_FOR_CARD_GENERATION: 400,
        RAGCardGenerationErrorCode.SECTION_NOT_FOUND: 404,
        RAGCardGenerationErrorCode.SECTION_NOT_READY: 409,
        RAGCardGenerationErrorCode.INVALID_GENERATION_MODE: 400,
        RAGCardGenerationErrorCode.ONTOLOGY_VERSION_NOT_FOUND: 400,
        RAGCardGenerationErrorCode.METADATA_SCHEMA_NOT_FOUND: 400,
        RAGCardGenerationErrorCode.PROMPT_TEMPLATE_NOT_FOUND: 400,
        RAGCardGenerationErrorCode.RAG_CARD_GENERATION_ALREADY_RUNNING: 409,
        RAGCardGenerationErrorCode.LLM_GATEWAY_UNAVAILABLE: 500,
        RAGCardGenerationErrorCode.LLM_TIMEOUT: 504,
        RAGCardGenerationErrorCode.INVALID_LLM_OUTPUT: 422,
        RAGCardGenerationErrorCode.INVALID_DOC_TYPE: 422,
        RAGCardGenerationErrorCode.DOC_ID_CONFLICT: 409,
        RAGCardGenerationErrorCode.CARD_BODY_EMPTY: 422,
    }
    return _MAP[code]


# ---------------------------------------------------------------------------
# RAGCardGenerationJob model
# ---------------------------------------------------------------------------


class RAGCardGenerationJob(BaseModel):
    """Задание генерации RAG-карточек (SETUP-05, DTO-59).

    Storage: PostgreSQL (план), MVP — in-memory ``InMemoryRAGCardGenerationJobRepository``.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    generation_job_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    requested_by: str = Field(..., min_length=1)
    status: RAGCardGenerationJobStatus = RAGCardGenerationJobStatus.CREATED

    # --- progress counters ---
    total_sections: int = Field(0, ge=0)
    processed_sections: int = Field(0, ge=0)
    generated_cards: int = Field(0, ge=0)
    failed_sections: int = Field(0, ge=0)
    review_required_cards: int = Field(0, ge=0)

    # --- timing ---
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # --- config / error ---
    config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Конфигурация генерации: generation_mode (llm/template/hybrid), "
            "confidence_threshold, llm_model, prompt_template_version, "
            "ontology_version, metadata_schema_version, generation_request_id."
        ),
    )
    error_code: RAGCardGenerationErrorCode | None = None
    error_message: str | None = Field(None, max_length=4000)

    # --- invariants ---

    @model_validator(mode="after")
    def _counters_consistent(self) -> RAGCardGenerationJob:
        if self.processed_sections > self.total_sections:
            raise ValueError("processed_sections cannot exceed total_sections")
        if self.generated_cards + self.failed_sections > self.total_sections:
            raise ValueError("generated_cards + failed_sections cannot exceed total_sections")
        if self.review_required_cards > self.generated_cards:
            raise ValueError("review_required_cards cannot exceed generated_cards")
        return self

    @model_validator(mode="after")
    def _finished_after_started(self) -> RAGCardGenerationJob:
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must be >= started_at")
        return self

    # --- state machine ---

    def can_transition_to(self, new_status: RAGCardGenerationJobStatus) -> bool:
        return new_status in RAG_CARD_JOB_ALLOWED_TRANSITIONS.get(self.status, frozenset())

    def transition_to(self, new_status: RAGCardGenerationJobStatus) -> None:
        if not self.can_transition_to(new_status):
            raise InvalidRAGCardJobTransitionError(self.generation_job_id, self.status, new_status)
        self.status = new_status

    @property
    def is_terminal(self) -> bool:
        return not RAG_CARD_JOB_ALLOWED_TRANSITIONS.get(self.status, frozenset())
