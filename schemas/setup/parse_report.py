"""DocumentParseReport и ParseError DTO (SETUP-04).

DocumentParseReport — итоговый отчёт о парсинге одного документа
в рамках ParseJob. Создаётся ParseService по завершении обработки документа
и передаётся в Setup Orchestrator и Frontend.

ParseError — компактный DTO ошибки для HTTP-ответов API
(используется в списках ошибок и batch-ответах).

Source of truth — SETUP-04 spec §15.4.
Storage — PostgreSQL, таблица parse_reports (одна запись на документ на job).
          Большие детали ошибок хранятся в processing_log.
          MVP: in-memory dict в ParseService.
Producer — SVC-07 Document Parser Service.
Consumers — SVC-04 Setup Orchestrator, SVC-01 Frontend UI, SVC-36 Audit Service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.setup.parse_job import ParseErrorCode, ParserStrategy
from schemas.setup.parse_job_document import ParseJobDocumentStatus

# ---------------------------------------------------------------------------
# ParseError — API-уровень
# ---------------------------------------------------------------------------


class ParseError(BaseModel):
    """Ошибка парсинга одного документа, используемая в HTTP-ответах.

    Не хранится самостоятельно: является частью batch-ответов и отчётов.
    Использующие сервисы: SVC-02 API Gateway, SVC-01 Frontend UI.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_document_id: str = Field(
        ..., min_length=1, description="ID исходного документа с ошибкой."
    )
    filename: str = Field(
        ..., min_length=1, max_length=255, description="Имя файла для отображения в UI."
    )
    error_code: ParseErrorCode = Field(..., description="Машиночитаемый код ошибки.")
    message: str = Field(
        ..., min_length=1, max_length=2000, description="Человекочитаемое описание."
    )
    parser_strategy: ParserStrategy | None = Field(
        None, description="Стратегия, которая применялась (None если ошибка до классификации)."
    )
    retryable: bool = Field(
        ..., description="True если повторный запуск ParseJob может решить проблему."
    )


# ---------------------------------------------------------------------------
# SectionsSummary — вложенная структура для DocumentParseReport.summary
# ---------------------------------------------------------------------------


class SectionsSummary(BaseModel):
    """Сводная статистика секций документа."""

    model_config = ConfigDict(extra="forbid")

    sections_count: int = Field(0, ge=0, description="Всего извлечённых секций.")
    sections_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Количество секций по типу: {'schema': 3, 'glossary': 5, ...}.",
    )
    low_confidence_sections: int = Field(0, ge=0, description="Секций с confidence ниже порога.")


# ---------------------------------------------------------------------------
# DocumentParseReport
# ---------------------------------------------------------------------------


class DocumentParseReport(BaseModel):
    """Итоговый отчёт о парсинге одного документа в рамках ParseJob.

    Создаётся после завершения или ошибки обработки документа.
    Хранит агрегированные счётчики; детальный лог — в SourceProcessingLogEntry.

    Storage: PostgreSQL, таблица parse_reports.
    MVP: in-memory в ParseService (SVC-07).
    """

    model_config = ConfigDict(extra="forbid")

    parse_report_id: str = Field(..., min_length=1, description="UUID отчёта.")
    parse_job_id: str = Field(..., min_length=1, description="FK → parse_jobs.parse_job_id.")
    source_document_id: str = Field(
        ..., min_length=1, description="FK → source_documents.source_document_id."
    )
    status: ParseJobDocumentStatus = Field(..., description="Итоговый статус документа в задании.")
    parser_strategy: ParserStrategy | None = Field(
        None, description="Применённая стратегия парсинга."
    )
    summary: SectionsSummary = Field(
        default_factory=lambda: SectionsSummary(
            sections_count=0,
            sections_by_type={},
            low_confidence_sections=0,
        ),
        description="Агрегированная статистика по секциям.",
    )
    errors: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Список ошибок: каждая запись содержит code, message, context.",
    )
    warnings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Список предупреждений: low_confidence, empty_sections и др.",
    )
    created_at: datetime = Field(..., description="Время создания отчёта (UTC).")
