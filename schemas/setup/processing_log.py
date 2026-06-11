"""SourceDocumentProcessingLog DTO (SETUP-03 / T-S03-003).

Журнал событий обработки документа: парсинг, генерация карточек, индексация,
ошибки. Каждая запись неизменяема. event_id обеспечивает идемпотентность.

Source of truth — SETUP-03 spec §15.2 (SourceProcessingLogDTO).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProcessingLogLevel(StrEnum):
    """Уровень лог-записи (зеркало stdlib logging)."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ProcessingLogStep(StrEnum):
    """Шаги pipeline обработки документа (§11.1 спека).

    Используется для фильтрации processing log по этапам.
    """

    UPLOAD = "upload"
    REGISTRATION = "registration"
    METADATA_EXTRACTION = "metadata_extraction"
    PARSING = "parsing"
    SECTION_EXTRACTION = "section_extraction"
    RAG_CARD_GENERATION = "rag_card_generation"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    REVIEW = "review"
    PUBLISH = "publish"
    CLEANUP = "cleanup"
    RETRY = "retry"  # T-S03-021: ручной retry


class SourceProcessingLogEntry(BaseModel):
    """Единичная запись processing log.

    Неизменяема после создания. event_id для идемпотентности.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    processing_log_id: str = Field(..., min_length=1)
    source_document_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    step: ProcessingLogStep
    level: ProcessingLogLevel = ProcessingLogLevel.INFO
    message: str = Field(..., min_length=1, max_length=4000)
    error_code: str | None = Field(default=None, max_length=128)
    event_id: str = Field(..., min_length=1, max_length=128)
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class SourceProcessingLogDTO(BaseModel):
    """Ответ GET /sources/{id}/processing-log."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    items: list[SourceProcessingLogEntry] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
