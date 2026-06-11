"""DTOs для SETUP-03 read endpoints (T-S03-012..015).

Все ответы под /sources префиксом. Каждый DTO с extra="forbid" — любое
изменение surface ловится contract-тестом.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from schemas.setup.lineage import LineageCounters, SourceLineageRelation
from schemas.setup.processing_log import (
    ProcessingLogLevel,
    ProcessingLogStep,
    SourceProcessingLogEntry,
)
from schemas.setup.source_document import SourceDocumentStatus
from schemas.setup.status_history import ChangedByType


class SourceDocumentListItemDTO(BaseModel):
    """Элемент списка GET /sources (агрегированный вид)."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    setup_job_id: str
    filename: str
    document_kind: str | None
    content_type: str
    size_bytes: int
    checksum_short: str  # первые 12 hex символов
    status: SourceDocumentStatus
    uploaded_by: str
    uploaded_at: datetime
    parsed_sections_count: int = 0
    rag_cards_count: int = 0
    chunks_count: int = 0
    last_error: str | None = None


class PaginationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    total: int = Field(default=0, ge=0)


class ListSourcesResponse(BaseModel):
    """Ответ GET /sources."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    items: list[SourceDocumentListItemDTO] = Field(default_factory=list)
    pagination: PaginationDTO


class SourceDocumentDetailsDTO(BaseModel):
    """Ответ GET /sources/{id} — полная карточка."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    setup_job_id: str
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    checksum: str
    checksum_algorithm: str = "sha256"
    storage_path: str | None  # masked для не-admin
    status: SourceDocumentStatus
    document_kind: str | None
    detected_language: str | None
    uploaded_by: str
    uploaded_at: datetime
    parsed_at: datetime | None
    error_message: str | None
    user_metadata: dict[str, Any] = Field(default_factory=dict)
    system_metadata: dict[str, Any] = Field(default_factory=dict)
    counters: LineageCounters = Field(default_factory=LineageCounters)
    last_status_change: datetime | None = None


class StatusHistoryEntryDTO(BaseModel):
    """Элемент истории статусов (для API)."""

    model_config = ConfigDict(extra="forbid")

    status_history_id: str
    source_document_id: str
    old_status: SourceDocumentStatus | None
    new_status: SourceDocumentStatus
    reason: str | None
    event_id: str
    changed_by_type: ChangedByType
    changed_by_id: str
    changed_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class StatusHistoryResponse(BaseModel):
    """Ответ GET /sources/{id}/status-history."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    items: list[StatusHistoryEntryDTO]
    pagination: PaginationDTO


class ProcessingLogEntryDTO(BaseModel):
    """Элемент processing log (для API)."""

    model_config = ConfigDict(extra="forbid")

    processing_log_id: str
    source_document_id: str
    setup_job_id: str
    step: ProcessingLogStep
    level: ProcessingLogLevel
    message: str
    error_code: str | None
    event_id: str
    created_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class ProcessingLogResponse(BaseModel):
    """Ответ GET /sources/{id}/processing-log."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    items: list[ProcessingLogEntryDTO]
    pagination: PaginationDTO


class LineageRelationDTO(BaseModel):
    """Lineage relation для API."""

    model_config = ConfigDict(extra="forbid")

    lineage_id: str
    source_document_id: str
    target_type: str
    target_id: str
    relation_type: str
    created_by_service: str
    event_id: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageResponse(BaseModel):
    """Ответ GET /sources/{id}/lineage."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    relations: list[LineageRelationDTO]
    counters: LineageCounters


# ============================================================
# SETUP-03 / T-S03-017: PATCH /sources/{id}/metadata response
# ============================================================


class PatchSourceMetadataResponse(BaseModel):
    """Ответ PATCH /sources/{id}/metadata."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    setup_job_id: str
    user_metadata: dict[str, Any]
    updated_at: datetime
    message: str | None = None


# ============================================================
# SETUP-03 / T-S03-018: DELETE /sources/{id} response
# ============================================================


class RemoveSourceResponse(BaseModel):
    """Ответ DELETE /sources/{id}."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    setup_job_id: str
    status: str  # "removed"
    message: str | None = None


# ============================================================
# SETUP-03 / T-S03-021: POST /sources/{id}/retry response
# ============================================================


class RetrySourceResponse(BaseModel):
    """Ответ POST /sources/{id}/retry."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    setup_job_id: str
    status: str  # после reset — обычно "waiting_for_parsing"
    from_step: str
    message: str | None = None


# ============================================================
# Adapter helpers — Pydantic-model → DTO
# ============================================================


def to_status_history_dto(entry: object) -> StatusHistoryEntryDTO:
    """Конвертирует SourceStatusHistoryEntry → API DTO."""
    from schemas.setup.status_history import SourceStatusHistoryEntry

    assert isinstance(entry, SourceStatusHistoryEntry)
    return StatusHistoryEntryDTO(**entry.model_dump())


def to_processing_log_dto(entry: SourceProcessingLogEntry) -> ProcessingLogEntryDTO:
    return ProcessingLogEntryDTO(**entry.model_dump())


def to_lineage_relation_dto(rel: SourceLineageRelation) -> LineageRelationDTO:
    return LineageRelationDTO(
        lineage_id=rel.lineage_id,
        source_document_id=rel.source_document_id,
        target_type=rel.target_type.value,
        target_id=rel.target_id,
        relation_type=rel.relation_type.value,
        created_by_service=rel.created_by_service,
        event_id=rel.event_id,
        created_at=rel.created_at,
        metadata=rel.metadata,
    )
