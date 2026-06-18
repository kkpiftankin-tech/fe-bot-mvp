"""SourceDocumentDTO (DTO-09) — исходный документ, загруженный пользователем.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-09.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common.defaults import MAX_FILE_SIZE_BYTES, SUPPORTED_CONTENT_TYPES


class SourceDocumentStatus(StrEnum):
    """Lifecycle статусы документа в Source Registry.

    Расширено в SETUP-03 / T-S03-001: добавлены 13 новых статусов из §3 спека.
    Старые статусы (UPLOADED, PARSED, CONVERTED, FAILED, FAILED_VALIDATION,
    ARCHIVED, REMOVED) сохранены для обратной совместимости с SETUP-01/02.
    """

    # Legacy (SETUP-01/02)
    UPLOADED = "uploaded"
    PARSED = "parsed"
    CONVERTED = "converted"
    FAILED = "failed"
    FAILED_VALIDATION = "failed_validation"  # T-S02-001: backend validation rejected
    ARCHIVED = "archived"
    REMOVED = "removed"  # T-S02-001: soft-delete via DELETE /documents/{id}

    # SETUP-03 / T-S03-001: extended lifecycle
    REGISTERED = "registered"  # запись создана в Source Registry
    METADATA_EXTRACTED = "metadata_extracted"  # technical metadata извлечена
    WAITING_FOR_PARSING = "waiting_for_parsing"
    PARSING = "parsing"
    PARSE_FAILED = "parse_failed"
    SECTIONS_EXTRACTED = "sections_extracted"
    RAG_CARDS_GENERATING = "rag_cards_generating"
    RAG_CARDS_GENERATED = "rag_cards_generated"
    REVIEW_REQUIRED = "review_required"
    PROCESSING_FAILED = "processing_failed"
    READY_FOR_INDEXING = "ready_for_indexing"
    PUBLISHED = "published"  # вошёл в активную KB version
    DEPRECATED = "deprecated"  # устарел, не используется в новой KB


class DocumentKind(StrEnum):
    REQUIREMENTS = "requirements"
    SCHEMA = "schema"
    TASK_LIST = "task_list"
    ANALYTICS = "analytics"
    GLOSSARY = "glossary"
    VALIDATION = "validation"
    OTHER = "other"


_SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$|^[a-f0-9]{64}$")


class SourceDocument(BaseModel):
    """Исходный документ, зарегистрированный в Source Registry."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    source_document_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1)
    storage_path: str = Field(..., min_length=1)
    size_bytes: int = Field(..., gt=0)
    checksum: str = Field(..., min_length=64)
    status: SourceDocumentStatus = SourceDocumentStatus.UPLOADED
    detected_language: str | None = Field(None, max_length=8)
    document_kind: DocumentKind | None = None
    uploaded_by: str = Field(..., min_length=1)
    uploaded_at: datetime
    parsed_at: datetime | None = None
    error_message: str | None = Field(None, max_length=4000)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_type")
    @classmethod
    def _supported_content_type(cls, v: str) -> str:
        if v not in SUPPORTED_CONTENT_TYPES:
            raise ValueError(f"Unsupported content_type: {v!r}")
        return v

    @field_validator("size_bytes")
    @classmethod
    def _size_within_limit(cls, v: int) -> int:
        if v > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size {v} bytes exceeds limit {MAX_FILE_SIZE_BYTES} bytes")
        return v

    @field_validator("checksum")
    @classmethod
    def _checksum_is_sha256(cls, v: str) -> str:
        if not _SHA256_PATTERN.match(v):
            raise ValueError(
                "checksum must be SHA-256 (64 hex chars, optionally prefixed with 'sha256:')"
            )
        # Нормализуем к виду без префикса.
        return v[len("sha256:") :] if v.startswith("sha256:") else v
