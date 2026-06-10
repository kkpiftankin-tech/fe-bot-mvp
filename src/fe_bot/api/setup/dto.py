"""HTTP request/response DTO для setup API.

Эти DTO — обёртки над DTO-07 для конкретных endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from schemas.setup.rag_setup_job import SetupJobStatus
from schemas.setup.upload_errors import UploadFileError


class CreateSetupJobRequest(BaseModel):
    """POST /api/v1/setup/jobs."""

    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(..., min_length=3, max_length=128)
    domain: str | None = Field(None, max_length=64)
    description: str | None = Field(None, max_length=2000)
    tags: list[str] = Field(default_factory=list)
    embedding_model: str | None = Field(None, max_length=128)
    review_policy: str = Field("strict", pattern=r"^(strict|allow_warnings)$")
    retrieval_test_profile: str = Field("basic", pattern=r"^(basic|domain|custom)$")


class SetupJobResponse(BaseModel):
    """Ответ для большинства setup endpoints."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    user_id: str
    project_name: str
    status: SetupJobStatus
    current_step: str | None
    progress_percent: float
    source_documents_count: int
    error_count: int
    warning_count: int
    started_at: datetime | None
    finished_at: datetime | None
    knowledge_base_version: str | None
    message: str | None = None


class SetupProgressResponse(BaseModel):
    """Ответ GET /api/v1/setup/{id}/progress."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    status: SetupJobStatus
    current_step: str | None
    progress_percent: float
    error_count: int
    warning_count: int


class SourceDocumentResponse(BaseModel):
    """Ответ для endpoint'ов работы с документами (T-S01-013/015)."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    setup_job_id: str
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    status: str
    uploaded_by: str
    uploaded_at: datetime
    storage_path: str | None = None  # для admin / debug; обычным пользователям None


class UploadSummary(BaseModel):
    """Summary-счётчики batch'а (SETUP-02 / T-S02-003).

    Инвариант: files_total = files_uploaded + files_rejected + duplicates_detected.
    """

    model_config = ConfigDict(extra="forbid")

    files_total: int = Field(..., ge=0)
    files_uploaded: int = Field(..., ge=0)
    files_rejected: int = Field(..., ge=0)
    duplicates_detected: int = Field(..., ge=0)


class UploadDocumentsResponse(BaseModel):
    """Ответ POST /api/v1/setup/{id}/documents.

    v2 (SETUP-02 / T-S02-003): добавлены `upload_batch_id`, `summary`, `errors`.
    Старые поля `uploaded` и `skipped_duplicates` сохранены для backward
    compatibility с v1-клиентами; новые клиенты используют `summary` + `errors`.
    """

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    upload_batch_id: str | None = None  # v2: id batch'а для idempotency / audit
    summary: UploadSummary | None = None  # v2: счётчики
    uploaded: list[SourceDocumentResponse]
    skipped_duplicates: list[SourceDocumentResponse]
    errors: list[UploadFileError] = Field(default_factory=list)  # v2: rejected files
    job_status: SetupJobStatus
    message: str | None = None


class ListDocumentsResponse(BaseModel):
    """Ответ GET /api/v1/setup/{id}/documents."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    documents: list[SourceDocumentResponse]
    count: int


class VectorIndexSummary(BaseModel):
    """Краткая сводка vector_index для ответа /run и /reindex."""

    model_config = ConfigDict(extra="forbid")

    index_version: str
    status: str
    embedding_model: str
    chunks_count: int
    indexed_chunks_count: int
    failed_chunks_count: int
    collection_names: list[str]


class RunPipelineResponse(BaseModel):
    """Ответ POST /api/v1/setup/{id}/run (T-S01-022, T-S01-032)."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    final_status: SetupJobStatus
    documents_total: int
    documents_parsed: int
    documents_failed: int
    sections_extracted: int
    cards_generated: int
    cards_review_required: int
    cards_used_fallback: int
    cards_metadata_validated: int = 0
    validation_warnings: int = 0
    validation_failed: int = 0
    cards_approved_auto: int = 0
    chunks_total: int = 0
    chunks_indexed: int = 0
    chunks_failed: int = 0
    vector_index: VectorIndexSummary | None = None
    errors: list[str]
    message: str | None = None


class ReindexResponse(BaseModel):
    """Ответ POST /api/v1/setup/{id}/reindex (T-S01-034)."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    index_version: str
    chunks_total: int
    chunks_indexed: int
    chunks_failed: int
    vector_index: VectorIndexSummary
    errors: list[str]
    message: str | None = None


class RAGCardSummary(BaseModel):
    """Краткое представление карточки для списков (T-S01-027)."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    doc_type: str
    title: str
    version: str
    status: str
    confidence_level: str | None
    domain: list[str]
    phase: list[str]
    retrieval_tags: list[str]
    source_document_ids: list[str]
    created_at: datetime
    updated_at: datetime
    body_preview: str | None = None  # первые 500 символов; полный body — по include=body
    body_markdown: str | None = None  # только при include=body
    history: list[str] = []


class ListCardsResponse(BaseModel):
    """Ответ GET /api/v1/setup/{id}/rag-cards (T-S01-027)."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    cards: list[RAGCardSummary]
    count: int
    filters: dict[str, str | None]


class ReviewRAGCardRequest(BaseModel):
    """Запрос POST /api/v1/setup/{id}/rag-cards/{doc_id}/review (T-S01-026)."""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(..., pattern=r"^(approve|reject|edit|regenerate)$")
    comment: str | None = Field(None, max_length=2000)
    updated_title: str | None = Field(None, max_length=512)
    updated_body_markdown: str | None = None


class ReviewRAGCardResponse(BaseModel):
    """Ответ review-эндпойнта."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    decision: str
    affected_doc_id: str
    new_doc_id: str | None = None  # для edit — id новой версии
    new_status: str
    message: str | None = None


# ---------- T-S01-037: retrieval-tests ----------


class GoldenQueryDTO(BaseModel):
    """Один пункт golden dataset для retrieval-eval."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000)
    expected_doc_ids: list[str] = Field(..., min_length=1)
    doc_types: list[str] | None = None
    description: str | None = Field(None, max_length=1000)


class RunRetrievalTestsRequest(BaseModel):
    """POST /setup/{id}/retrieval-tests body."""

    model_config = ConfigDict(extra="forbid")

    golden_queries: list[GoldenQueryDTO] = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)
    threshold_recall_at_5: float | None = Field(None, ge=0.0, le=1.0)


class PerQueryEvalDTO(BaseModel):
    """Результат eval для одного запроса."""

    model_config = ConfigDict(extra="forbid")

    query: str
    expected_doc_ids: list[str]
    retrieved_doc_ids: list[str]
    recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float
    is_no_context: bool
    error_message: str | None = None


class EvalReportResponse(BaseModel):
    """Ответ POST /setup/{id}/retrieval-tests (T-S01-037)."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    queries_total: int
    queries_errored: int
    top_k: int
    threshold_recall_at_5: float
    mean_recall_at_k: float
    mean_precision_at_k: float
    mean_reciprocal_rank: float
    no_context_rate: float
    passed: bool
    per_query: list[PerQueryEvalDTO]
    message: str | None = None


# ---------- T-S01-039: publish + report ----------


class PublishKBRequest(BaseModel):
    """POST /setup/{id}/publish body."""

    model_config = ConfigDict(extra="forbid")

    eval_report: EvalReportResponse | None = None
    comment: str | None = Field(None, max_length=2000)


class PublishKBResponse(BaseModel):
    """Ответ POST /setup/{id}/publish (T-S01-039)."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    knowledge_base_version: str
    status: str
    is_active: bool
    published_by: str | None
    published_at: datetime | None
    index_version: str | None
    rag_card_count: int
    chunk_count: int
    message: str | None = None


class ProcessingReportResponse(BaseModel):
    """GET /setup/{id}/report — итоговая сводка по job (T-S01-039)."""

    model_config = ConfigDict(extra="forbid")

    setup_job_id: str
    status: SetupJobStatus
    project_name: str
    user_id: str
    progress_percent: float
    error_count: int
    warning_count: int
    documents_count: int
    cards_count: int
    cards_approved: int
    cards_review_required: int
    cards_deprecated: int
    knowledge_base_version: str | None
    knowledge_base_status: str | None
    knowledge_base_is_active: bool
    chunks_indexed: int
    index_version: str | None
    eval_passed: bool | None
    started_at: datetime | None
    finished_at: datetime | None
