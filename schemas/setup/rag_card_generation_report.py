"""CardGenerationReportDTO + CardValidationReportDTO (SETUP-05).

CardGenerationReport — итоговый агрегированный отчёт по RAGCardGenerationJob.
CardValidationReport — precheck-результат для одной карточки (blocking errors +
warnings) до сохранения; отделён от full metadata validation (SETUP-07).

Source of truth — docs/03-architecture/services/data-transfer-objects.md DTO-64, DTO-65.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.setup.rag_card_generation_job import RAGCardGenerationJobStatus


class CardGenerationSummary(BaseModel):
    """Агрегированная статистика по RAGCardGenerationJob."""

    model_config = ConfigDict(extra="forbid")

    total_sections: int = Field(0, ge=0)
    processed_sections: int = Field(0, ge=0)
    generated_cards: int = Field(0, ge=0)
    failed_sections: int = Field(0, ge=0)
    review_required_cards: int = Field(0, ge=0)
    cards_by_type: dict[str, int] = Field(default_factory=dict)


class CardGenerationReportDTO(BaseModel):
    """Итоговый report по job.

    Storage: PostgreSQL `rag_card_validation_reports` (план); MVP — in-memory.
    Last-write-wins по generation_job_id.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    generation_report_id: str = Field(..., min_length=1)
    generation_job_id: str = Field(..., min_length=1)
    status: RAGCardGenerationJobStatus
    summary: CardGenerationSummary = Field(
        default_factory=lambda: CardGenerationSummary(
            total_sections=0,
            processed_sections=0,
            generated_cards=0,
            failed_sections=0,
            review_required_cards=0,
            cards_by_type={},
        )
    )
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class CardValidationReportDTO(BaseModel):
    """Precheck-результат для одной карточки.

    Storage: PostgreSQL `rag_card_validation_reports` (общий с CardGenerationReport).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    validation_report_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    passed: bool
    errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Blocking errors. Codes: DOC_ID_MISSING, DOC_TYPE_INVALID, "
            "SOURCE_FILES_EMPTY, SOURCE_SECTIONS_EMPTY, CARD_BODY_EMPTY, "
            "FRONT_MATTER_INVALID."
        ),
    )
    warnings: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Non-blocking warnings. Codes: RETRIEVAL_TAGS_EMPTY, MISSING_OPTIONAL_METADATA."
        ),
    )
    checked_at: datetime
