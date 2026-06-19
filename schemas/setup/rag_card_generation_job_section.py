"""RAGCardGenerationJobSection DTO (SETUP-05) — per-section запись внутри job.

Связывает RAGCardGenerationJob с конкретной ParsedSection, фиксирует выбранный
doc_type, сгенерированный doc_id, confidence_level и тайминг. Эквивалент
ParseJobDocument из SETUP-04 для генерации карточек.

Source of truth — docs/03-architecture/services/data-transfer-objects.md DTO-60.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.setup.rag_card_generation_job import RAGCardGenerationErrorCode


class RAGCardGenerationJobSectionStatus(StrEnum):
    """Статус обработки одной секции внутри RAGCardGenerationJob."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CardConfidenceLevel(StrEnum):
    """Уровень уверенности генерации карточки (high/medium/low)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RAGCardGenerationJobSection(BaseModel):
    """Запись о генерации одной карточки в рамках job.

    Storage: PostgreSQL `rag_card_generation_job_sections` (план); MVP — in-memory.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    generation_job_section_id: str = Field(..., min_length=1)
    generation_job_id: str = Field(..., min_length=1)
    section_id: str = Field(..., min_length=1)
    source_document_id: str = Field(..., min_length=1)
    status: RAGCardGenerationJobSectionStatus = RAGCardGenerationJobSectionStatus.PENDING
    target_doc_type: str | None = Field(
        None,
        description=("Целевой doc_type, определённый DocTypeDetector. None до момента детекции."),
    )
    generated_doc_id: str | None = Field(
        None,
        description="ID созданной RAG-карточки. None до успешной генерации.",
    )
    confidence_level: CardConfidenceLevel | None = None

    # --- timing ---
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(None, ge=0)

    # --- error ---
    error_code: RAGCardGenerationErrorCode | None = None
    error_message: str | None = Field(None, max_length=4000)

    # --- warnings (non-blocking issues from precheck/ontology) ---
    warnings: list[dict[str, Any]] = Field(default_factory=list)

    # --- open metadata ---
    metadata: dict[str, Any] = Field(default_factory=dict)

    # --- invariants ---

    @model_validator(mode="after")
    def _finished_after_started(self) -> RAGCardGenerationJobSection:
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must be >= started_at")
        return self
