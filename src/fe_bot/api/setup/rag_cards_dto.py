"""API DTO для SETUP-05 RAG cards endpoints (T-S05-027)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from schemas.common.defaults import DEFAULT_LLM_MODEL
from schemas.setup.rag_card_generation_job import (
    RAGCardGenerationErrorCode,
    RAGCardGenerationJobStatus,
)


class _Forbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ============================================================
# POST /rag-cards/generate (T-S05-028)
# ============================================================


class GenerateRAGCardsOptions(_Forbid):
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    allow_multiple_cards_per_section: bool = False
    mark_low_confidence_as_review_required: bool = True
    save_llm_trace: bool = False


class GenerateRAGCardsRequest(_Forbid):
    section_ids: list[str] | None = None
    source_document_ids: list[str] | None = None
    generation_mode: str = Field(
        default="llm",
        pattern=r"^(llm|template|hybrid)$",
    )
    ontology_version: str = "ontology_v1"
    metadata_schema_version: str = "rag_metadata_v1"
    prompt_template_version: str = "rag_card_prompts_v1"
    llm_model: str = DEFAULT_LLM_MODEL
    options: GenerateRAGCardsOptions = Field(default_factory=GenerateRAGCardsOptions)
    generation_request_id: str | None = None


class RAGCardGenerationJobResponse(_Forbid):
    generation_job_id: str
    setup_job_id: str
    requested_by: str
    status: RAGCardGenerationJobStatus
    total_sections: int
    processed_sections: int = 0
    generated_cards: int = 0
    failed_sections: int = 0
    review_required_cards: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    error_code: RAGCardGenerationErrorCode | None = None
    error_message: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# GET /rag-cards (list) + /rag-cards/{doc_id} (details) + /preview
# ============================================================


class PaginationDTO(_Forbid):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class RAGCardListItemDTO(_Forbid):
    doc_id: str
    setup_job_id: str
    card_version: str
    doc_type: str
    title: str
    status: str
    confidence_level: str | None = None
    primary_source_section_id: str | None = None
    source_document_ids: list[str] = Field(default_factory=list)
    retrieval_tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    review_required_reason: str | None = None


class RAGCardListResponse(_Forbid):
    setup_job_id: str
    items: list[RAGCardListItemDTO]
    pagination: PaginationDTO


class RAGCardSourceTraceDTO(_Forbid):
    source_link_id: str
    source_document_id: str
    source_section_id: str
    relation_type: str


class RAGCardDetailsDTO(_Forbid):
    doc_id: str
    setup_job_id: str
    card_version: str
    doc_type: str
    title: str
    status: str
    confidence_level: str | None = None
    front_matter: dict[str, Any]
    body_markdown: str
    source_document_ids: list[str]
    source_section_ids: list[str]
    review_required_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    markdown_artifact_id: str | None = None
    available_versions: list[str] = Field(default_factory=list)


class RAGCardPreviewDTO(_Forbid):
    doc_id: str
    card_version: str
    doc_type: str
    title: str
    status: str
    confidence_level: str | None = None
    front_matter: dict[str, Any]
    body_markdown: str
    source_trace: list[RAGCardSourceTraceDTO] = Field(default_factory=list)


# ============================================================
# POST /rag-cards/{doc_id}/regenerate (T-S05-030)
# ============================================================


class RegenerateRAGCardRequest(_Forbid):
    reason: str = Field(..., min_length=1, max_length=2000)
    override_doc_type: str | None = None
    regenerate_request_id: str | None = None


class RegenerateRAGCardResponse(_Forbid):
    doc_id: str
    new_card_version: str
    generation_job_id: str
    status: RAGCardGenerationJobStatus
    message: str


# ============================================================
# POST /rag-card-generation-jobs/{job_id}/cancel (T-S05-031)
# ============================================================


class CancelRAGCardJobResponse(_Forbid):
    generation_job_id: str
    status: RAGCardGenerationJobStatus
    message: str


# ============================================================
# GET /rag-card-generation-jobs/{job_id}/report
# ============================================================


class CardGenerationSummaryDTO(_Forbid):
    total_sections: int
    processed_sections: int
    generated_cards: int
    failed_sections: int
    review_required_cards: int
    cards_by_type: dict[str, int]


class RAGCardGenerationReportResponse(_Forbid):
    generation_report_id: str
    generation_job_id: str
    status: RAGCardGenerationJobStatus
    summary: CardGenerationSummaryDTO
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    created_at: datetime
