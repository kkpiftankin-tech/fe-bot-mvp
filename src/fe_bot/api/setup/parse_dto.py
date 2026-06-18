"""Pydantic DTO для SETUP-04 parse endpoints (T-S04-023..026)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from schemas.setup.parse_job import ParseErrorCode, ParseJobStatus, ParserStrategy
from schemas.setup.parse_job_document import ParseJobDocumentStatus
from schemas.setup.parsed_section import ParsedSectionStatus, SectionType


class _Forbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ============================================================
# POST /parse-jobs
# ============================================================


class CreateParseJobRequest(_Forbid):
    config: dict[str, Any] | None = Field(default=None)


class ParseJobResponse(_Forbid):
    parse_job_id: str
    setup_job_id: str
    status: ParseJobStatus
    total_documents: int
    processed_documents: int = 0
    failed_documents: int = 0
    total_sections: int = 0
    low_confidence_sections: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    error_code: ParseErrorCode | None = None
    error_message: str | None = None


# ============================================================
# GET /parse-jobs/{id}/report
# ============================================================


class DocumentReportDTO(_Forbid):
    source_document_id: str
    status: ParseJobDocumentStatus
    parser_strategy: ParserStrategy | None = None
    sections_count: int
    sections_by_type: dict[str, int]
    low_confidence_sections: int
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    created_at: datetime


class ParseJobReportResponse(_Forbid):
    parse_job_id: str
    setup_job_id: str
    status: ParseJobStatus
    documents: list[DocumentReportDTO]


# ============================================================
# GET /parse-jobs/{id}/sections
# ============================================================


class PaginationDTO(_Forbid):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class ParsedSectionListItemDTO(_Forbid):
    section_id: str
    source_document_id: str
    title: str
    section_type: SectionType
    section_status: ParsedSectionStatus
    confidence: float | None = None
    heading_path: list[str]
    section_index: int
    parent_section_id: str | None = None
    content_hash: str


class ParsedSectionsResponse(_Forbid):
    parse_job_id: str
    items: list[ParsedSectionListItemDTO]
    pagination: PaginationDTO


# ============================================================
# POST /cancel + retry
# ============================================================


class CancelParseJobResponse(_Forbid):
    parse_job_id: str
    status: ParseJobStatus
    message: str


class RetryParseDocumentResponse(_Forbid):
    parse_job_id: str
    source_document_id: str
    status: ParseJobDocumentStatus
    message: str
    new_parse_job_id: str | None = None
