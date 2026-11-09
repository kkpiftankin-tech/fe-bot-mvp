"""Pydantic DTO для SETUP-04 parse endpoints (T-S04-023..026)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from schemas.classifier.classification_result import FragmentClassificationResult
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
    # SETUP-12 (legacy, заменено SETUP-13 — см. ADR-HTC-09): больше не
    # заполняется, оставлено для секций, сохранённых до перехода.
    classification_method: str | None = None
    classification_state: dict[str, Any] | None = None
    # SETUP-13: путь по дереву классификаторов (opt-in via
    # FE_BOT_TAXONOMY_MODE=llm). None — классификация по дереву не
    # запускалась (rule_based mode).
    classifier_result: FragmentClassificationResult | None = None


class ParsedSectionsResponse(_Forbid):
    parse_job_id: str
    items: list[ParsedSectionListItemDTO]
    pagination: PaginationDTO


class ClassificationBitDTO(_Forbid):
    """Один активный бит classification_state с расшифровкой."""

    level: int
    bit_index: int
    class_slug: str
    display_name_ru: str
    doc_type_hint: str | None
    confidence: float | None
    is_primary: bool


class ParsedSectionDetailDTO(_Forbid):
    """Полная детализация секции для UI-detail-panel."""

    section_id: str
    parse_job_id: str
    source_document_id: str
    title: str
    heading_path: list[str]
    section_index: int
    parent_section_id: str | None
    section_type: SectionType
    section_status: ParsedSectionStatus
    confidence: float | None = None
    content_hash: str
    raw_text: str
    normalized_text: str
    start_offset: int | None
    end_offset: int | None
    metadata: dict[str, Any]
    classification_method: str | None = None
    classification_state: dict[str, Any] | None = None
    # Обогащённая расшифровка bitmap'а через таксономический реестр.
    classification_bits: list[ClassificationBitDTO] = Field(default_factory=list)
    # SETUP-13: путь по дереву классификаторов.
    classifier_result: FragmentClassificationResult | None = None


class ClassificationPromptDTO(_Forbid):
    """Prompt preview для одного уровня классификации.

    Рендерится текущим ClassificationPromptRenderer'ом; это не
    исторический prompt (он не сохраняется), а «как бы выглядел
    запрос СЕЙЧАС при текущем состоянии реестра».
    """

    level: int
    parent_path: str
    candidates_count: int
    free_slots_count: int
    rendered_prompt: str
    can_render: bool
    reason: str | None = None


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
