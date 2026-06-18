"""ParseJobDocument DTO (SETUP-04) — статус отдельного документа в рамках ParseJob.

Связывает ParseJob с SourceDocument и фиксирует результат парсинга
для каждого документа: стратегию, счётчики секций, тайминг, ошибки.

Source of truth — SETUP-04 spec §15.2.
Storage — PostgreSQL, таблица parse_job_documents.
MVP: in-memory dict в ParseService (SVC-07).
Producer — SVC-07 Document Parser Service.
Consumers — SVC-04 Setup Orchestrator, SVC-01 Frontend UI, SVC-36 Audit Service.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.setup.parse_job import ParseErrorCode, ParserStrategy


class ParseJobDocumentStatus(StrEnum):
    """Статус обработки конкретного документа в рамках ParseJob.

    Отличается от ParseJobStatus: здесь фокус на одном документе.
    """

    PENDING = "pending"  # в очереди, ещё не начат
    PROCESSING = "processing"  # активно парсится
    COMPLETED = "completed"  # успешно завершён
    FAILED = "failed"  # завершился с ошибкой
    SKIPPED = "skipped"  # пропущен (неподходящий статус документа)


class ParseJobDocument(BaseModel):
    """Запись о парсинге одного SourceDocument в рамках ParseJob.

    Создаётся при постановке документа в задание (status=pending).
    Обновляется при каждом изменении состояния обработки.

    Storage: PostgreSQL, таблица parse_job_documents.
    MVP: in-memory dict в ParseService (SVC-07).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    parse_job_document_id: str = Field(
        ..., min_length=1, description="UUID записи (суррогатный ключ)."
    )
    parse_job_id: str = Field(..., min_length=1, description="FK → parse_jobs.parse_job_id.")
    source_document_id: str = Field(
        ..., min_length=1, description="FK → source_documents.source_document_id."
    )
    status: ParseJobDocumentStatus = Field(
        ParseJobDocumentStatus.PENDING,
        description="Текущий статус обработки документа.",
    )
    parser_strategy: ParserStrategy | None = Field(
        None,
        description="Стратегия парсинга, определённая rule-based classifier'ом. "
        "None — до момента классификации.",
    )

    # --- section counters (заполняются после завершения парсинга) ---
    sections_count: int = Field(0, ge=0, description="Число успешно извлечённых секций.")
    low_confidence_sections_count: int = Field(
        0, ge=0, description="Секций с confidence ниже порога."
    )

    # --- timing ---
    started_at: datetime | None = Field(None, description="Время начала обработки документа.")
    finished_at: datetime | None = Field(None, description="Время завершения (успех или ошибка).")
    duration_ms: int | None = Field(
        None, ge=0, description="Длительность парсинга в мс. Вычисляется из started_at/finished_at."
    )

    # --- error ---
    error_code: ParseErrorCode | None = Field(None, description="Код ошибки при status=failed.")
    error_message: str | None = Field(None, max_length=4000, description="Описание ошибки.")

    # --- open metadata ---
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Расширяемые данные: detected_language, page_count, sheet_names и др.",
    )

    # --- invariants ---

    @model_validator(mode="after")
    def _low_confidence_not_exceed_total(self) -> ParseJobDocument:
        if self.low_confidence_sections_count > self.sections_count:
            raise ValueError("low_confidence_sections_count cannot exceed sections_count")
        return self

    @model_validator(mode="after")
    def _finished_after_started(self) -> ParseJobDocument:
        if (
            self.started_at is not None
            and self.finished_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError("finished_at must be >= started_at")
        return self
