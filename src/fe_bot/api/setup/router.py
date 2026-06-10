"""Router для setup endpoints.

12 endpoints из SETUP-01 §16.1. В S1 реализованы 4:
- POST /jobs
- GET /{id}
- GET /{id}/progress
- POST /{id}/cancel

Остальные возвращают 501 Not Implemented и реализуются в S2..S6.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from schemas.rag.knowledge_base_version import KBStatus
from schemas.rag.rag_card import CardStatus as _CardStatus
from schemas.setup.rag_setup_job import (
    InvalidTransitionError,
    RAGSetupJob,
    SetupJobStatus,
)
from schemas.setup.source_document import SourceDocument
from schemas.setup.upload_batch import UploadBatch, UploadBatchStatus
from schemas.setup.upload_errors import UploadFileError, http_status_for

from fe_bot.api.dependencies import (
    get_audit_service,
    get_batch_registry,
    get_card_registry,
    get_card_review,
    get_evaluation_service,
    get_idempotency_cache,
    get_kb_publish_service,
    get_kb_repository,
    get_metrics,
    get_orchestrator,
    get_pipeline,
    get_source_registry,
    get_upload_service,
    get_vector_indexer,
    require_permission,
)
from fe_bot.api.setup.dto import (
    CreateSetupJobRequest,
    EvalReportResponse,
    ListCardsResponse,
    ListDocumentsResponse,
    PerQueryEvalDTO,
    ProcessingReportResponse,
    PublishKBRequest,
    PublishKBResponse,
    RAGCardSummary,
    ReindexResponse,
    RemoveDocumentResponse,
    ReviewRAGCardRequest,
    ReviewRAGCardResponse,
    RunPipelineResponse,
    RunRetrievalTestsRequest,
    SetupJobResponse,
    SetupProgressResponse,
    SourceDocumentResponse,
    UploadDocumentsResponse,
    UploadSummary,
    VectorIndexSummary,
)
from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.auth.permissions import Permission
from fe_bot.auth.permissions import Role as _Role
from fe_bot.auth.service import Principal
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.card_review.service import (
    InvalidEditPayloadError,
    InvalidReviewStateError,
    RAGCardReviewService,
    ReviewDecision,
)
from fe_bot.setup.evaluation.service import (
    GoldenQuery,
    RAGEvaluationService,
)
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.pipeline import PipelineError, SetupPipeline
from fe_bot.setup.publish.service import (
    InMemoryKBRepository,
    KBPublishService,
    PublishNotReadyError,
)
from fe_bot.setup.repository import JobNotFoundError
from fe_bot.setup.source_registry.service import (
    InMemorySourceRegistry,
    SourceDocumentNotFoundError,
)
from fe_bot.setup.upload.batch_registry import InMemoryBatchRegistry
from fe_bot.setup.upload.idempotency import (
    InMemoryIdempotencyCache,
    make_cache_key,
)
from fe_bot.setup.upload.service import (
    DocumentUploadService,
    DuplicateStrategy,
    JobNotAcceptingUploadsError,
)
from fe_bot.setup.upload.validation import (
    UploadValidationError,
    check_filename_uniqueness,
    validate_batch_limits,
)
from fe_bot.storage.artifact_service import StorageError
from fe_bot.vector_index.service import VectorIndexerService

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])


def _to_response(job: RAGSetupJob, message: str | None = None) -> SetupJobResponse:
    return SetupJobResponse(
        setup_job_id=job.setup_job_id,
        user_id=job.user_id,
        project_name=job.project_name,
        status=job.status,
        current_step=job.current_step,
        progress_percent=job.progress_percent,
        source_documents_count=len(job.source_document_ids),
        error_count=job.error_count,
        warning_count=job.warning_count,
        started_at=job.started_at,
        finished_at=job.finished_at,
        knowledge_base_version=job.knowledge_base_version,
        message=message,
    )


# ---------- Реализованные endpoints (S1) ----------

@router.post(
    "/jobs",
    response_model=SetupJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create setup job (T-S01-009)",
)
def create_setup_job(
    payload: CreateSetupJobRequest,
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_CREATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
) -> SetupJobResponse:
    job = orchestrator.create_job(
        user_id=principal.user_id,
        project_name=payload.project_name,
    )
    return _to_response(job, message="Setup job created")


@router.get(
    "/{setup_job_id}",
    response_model=SetupJobResponse,
    summary="Get setup job status (T-S01-010)",
)
def get_setup_job(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_CREATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
) -> SetupJobResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if job.user_id != principal.user_id and not any(
        principal.has_permission(p) for p in (Permission.KB_PUBLISH,)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access job owned by another user",
        )
    return _to_response(job)


@router.get(
    "/{setup_job_id}/progress",
    response_model=SetupProgressResponse,
    summary="Get setup job progress (T-S01-010)",
)
def get_setup_progress(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_CREATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
) -> SetupProgressResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if job.user_id != principal.user_id and not principal.has_permission(Permission.KB_PUBLISH):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access job owned by another user",
        )
    return SetupProgressResponse(
        setup_job_id=job.setup_job_id,
        status=job.status,
        current_step=job.current_step,
        progress_percent=job.progress_percent,
        error_count=job.error_count,
        warning_count=job.warning_count,
    )


@router.post(
    "/{setup_job_id}/cancel",
    response_model=SetupJobResponse,
    summary="Cancel setup job (T-S01-011)",
)
def cancel_setup_job(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_CREATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
) -> SetupJobResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if job.user_id != principal.user_id and not principal.has_permission(Permission.KB_PUBLISH):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot cancel job owned by another user",
        )
    try:
        cancelled = orchestrator.cancel_job(setup_job_id)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _to_response(cancelled, message="Setup job cancelled")


# ---------- Скелетные endpoints (S2..S6) ----------

_NOT_IMPLEMENTED = HTTPException(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    detail="Endpoint scheduled for a later slice (S2..S6)",
)


# Permissions, дающие cross-job доступ (через привилегированные role).
# KB_REPORT_READ не входит: его имеет каждая роль (включая USER), но cross-job
# доступ должен быть привилегией auditor/admin, а не общедоступной.
_CROSS_JOB_PERMISSIONS = frozenset(
    {Permission.KB_PUBLISH, Permission.KB_CARD_REVIEW}
)

# Cross-job для report endpoint: дополнительно auditor (read-only audit).
_REPORT_CROSS_JOB_ROLES = frozenset({_Role.AUDITOR, _Role.ADMIN})


def _check_job_access(
    job: RAGSetupJob, principal: Principal, action: str = "access"
) -> None:
    """Owner может всё со своим job. Cross-job — нужна KB_PUBLISH или KB_CARD_REVIEW.

    KB_CARD_REVIEW даёт cross-job доступ потому что reviewer'у нужно видеть
    карточки в любом job (domain_expert не привязан к конкретному пользователю).
    """
    if job.user_id == principal.user_id:
        return
    if any(principal.has_permission(p) for p in _CROSS_JOB_PERMISSIONS):
        return
    # Специальное правило для report: auditor / admin читают любой job.
    if action == "report" and bool(principal.roles & _REPORT_CROSS_JOB_ROLES):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Cannot {action} job owned by another user",
    )


def _to_doc_response(
    doc: SourceDocument, *, include_storage_path: bool = False
) -> SourceDocumentResponse:
    return SourceDocumentResponse(
        source_document_id=doc.source_document_id,
        setup_job_id=doc.setup_job_id,
        filename=doc.filename,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        checksum=doc.checksum,
        status=doc.status.value,
        uploaded_by=doc.uploaded_by,
        uploaded_at=doc.uploaded_at,
        storage_path=doc.storage_path if include_storage_path else None,
    )


@router.post(
    "/{setup_job_id}/documents",
    response_model=UploadDocumentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload documents (T-S01-013)",
)
async def upload_documents(
    setup_job_id: str = Path(..., min_length=1),
    files: list[UploadFile] = File(default_factory=list),
    duplicate_strategy: DuplicateStrategy = Query(default=DuplicateStrategy.SKIP),
    upload_request_id: str | None = Query(default=None, max_length=128),
    principal: Principal = Depends(require_permission(Permission.KB_DOCUMENT_UPLOAD)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    upload_svc: DocumentUploadService = Depends(get_upload_service),
    idempotency: InMemoryIdempotencyCache = Depends(get_idempotency_cache),
    batch_registry: InMemoryBatchRegistry = Depends(get_batch_registry),
    audit: AuditService = Depends(get_audit_service),
    metrics: MetricsRegistry = Depends(get_metrics),
) -> UploadDocumentsResponse:
    """T-S02-005/006: batch-level pre-checks + per-file partial success.

    Поведение:
    - **Batch-level ошибки** (MISSING_FILES, BATCH_TOO_LARGE, INVALID_FILENAME
      duplicate_in_batch) → 4xx с HTTPException.
    - **Per-file ошибки** (UNSUPPORTED_FILE_TYPE, FILE_TOO_LARGE, EMPTY_FILE,
      INVALID_FILENAME) → собираются в `errors[]`, response 201 с partial summary.
    - **Duplicate per-file** → `skipped_duplicates[]`, не в errors[].
    """
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="upload to")

    # T-S02-007: idempotency check. Если совпадает — возвращаем кешированный.
    cache_key: str | None = None
    if upload_request_id:
        cache_key = make_cache_key(setup_job_id, upload_request_id)
        cached = idempotency.get(cache_key)
        if cached is not None:
            return cached
        # Fallback: возможно cache очищен, но batch уже существует в registry.
        existing_batch = batch_registry.get_by_request_id(
            setup_job_id, upload_request_id
        )
        if existing_batch is not None:
            # Конфликт: тот же request_id уже использован, но результат
            # вне TTL cache. Возвращаем 409, чтобы клиент знал что повтор
            # отвергнут не из-за валидации, а из-за идемпотентности.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"upload_request_id {upload_request_id!r} already used "
                    f"by batch {existing_batch.upload_batch_id!r}"
                ),
            )

    # ----- Batch-level pre-checks (T-S02-005/006) -----
    try:
        total_size = sum((f.size or 0) for f in files)
        validate_batch_limits(
            files_count=len(files), total_size_bytes=total_size
        )
        check_filename_uniqueness([f.filename or "" for f in files])
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=http_status_for(exc.code),
            detail={
                "error_code": exc.code.value,
                "message": str(exc),
                "details": exc.details,
            },
        ) from exc

    # T-S02-009: создаём UploadBatch в IN_PROGRESS до начала обработки файлов.
    upload_batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    batch = UploadBatch(
        upload_batch_id=upload_batch_id,
        setup_job_id=setup_job_id,
        user_id=principal.user_id,
        upload_request_id=upload_request_id,
        files_total=len(files),
        created_at=datetime.now(tz=UTC),
    )
    batch_registry.add(batch)

    uploaded: list[SourceDocumentResponse] = []
    skipped: list[SourceDocumentResponse] = []
    errors: list[UploadFileError] = []
    for upload in files:
        filename = upload.filename or ""
        try:
            data = await upload.read()
            result = upload_svc.upload(
                setup_job_id=setup_job_id,
                filename=filename,
                content_type=upload.content_type or "",
                data=data,
                uploaded_by=principal.user_id,
                duplicate_strategy=duplicate_strategy,
            )
        except UploadValidationError as exc:
            # Per-file ошибки идут в errors[], не fail-весь-batch (SETUP-02 §14.1).
            errors.append(
                UploadFileError(
                    filename=filename or "unknown",
                    error_code=exc.code,
                    message=str(exc),
                    details=exc.details,
                )
            )
            continue
        except JobNotAcceptingUploadsError as exc:
            # Этот статус job — batch-level, не должен оказаться в errors[]
            # (он fail-весь-batch при первом fail). Финализируем batch как FAILED.
            fail_batch = batch.model_copy(
                update={
                    "files_uploaded": len(uploaded),
                    "files_rejected": len(errors),
                    "duplicates_detected": len(skipped),
                }
            )
            with contextlib.suppress(Exception):
                fail_batch.transition_to(UploadBatchStatus.FAILED)
                batch_registry.update(fail_batch)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        except StorageError as exc:
            # T-S02-024: Object Storage недоступен — batch FAILED, 500 клиенту.
            fail_batch = batch.model_copy(
                update={
                    "files_uploaded": len(uploaded),
                    "files_rejected": len(errors),
                    "duplicates_detected": len(skipped),
                }
            )
            with contextlib.suppress(Exception):
                fail_batch.transition_to(UploadBatchStatus.FAILED)
                batch_registry.update(fail_batch)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_code": "OBJECT_STORAGE_UNAVAILABLE",
                    "message": str(exc),
                },
            ) from exc
        finally:
            await upload.close()

        doc_response = _to_doc_response(result.document)
        if result.was_duplicate:
            skipped.append(doc_response)
        else:
            uploaded.append(doc_response)

    # Свежий job-статус после возможных переходов.
    refreshed = orchestrator.get_job(setup_job_id)
    summary = UploadSummary(
        files_total=len(files),
        files_uploaded=len(uploaded),
        files_rejected=len(errors),
        duplicates_detected=len(skipped),
    )

    # T-S02-009: финализируем batch с counter'ами и terminal status.
    if len(uploaded) == len(files):
        terminal = UploadBatchStatus.COMPLETED
    elif len(uploaded) > 0:
        terminal = UploadBatchStatus.PARTIALLY_COMPLETED
    else:
        terminal = UploadBatchStatus.FAILED

    finalized_batch = batch.model_copy(
        update={
            "files_uploaded": len(uploaded),
            "files_rejected": len(errors),
            "duplicates_detected": len(skipped),
        }
    )
    finalized_batch.transition_to(terminal)
    batch_registry.update(finalized_batch)

    # T-S02-011: BATCH_COMPLETED audit + T-S02-012: upload_requests_total counter.
    audit.record(
        actor_id=principal.user_id,
        action=AuditAction.BATCH_COMPLETED,
        target_type="upload_batch",
        target_id=upload_batch_id,
        setup_job_id=setup_job_id,
        payload={
            "files_total": len(files),
            "files_uploaded": len(uploaded),
            "files_rejected": len(errors),
            "duplicates_detected": len(skipped),
            "terminal_status": terminal.value,
        },
    )
    metrics.inc(
        "upload_requests_total",
        labels={"outcome": terminal.value},
        help_text="Total upload batch requests by outcome",
    )

    message = (
        f"Uploaded {len(uploaded)} file(s), "
        f"skipped {len(skipped)} duplicate(s), "
        f"rejected {len(errors)}"
    )
    response = UploadDocumentsResponse(
        setup_job_id=setup_job_id,
        upload_batch_id=upload_batch_id,
        summary=summary,
        uploaded=uploaded,
        skipped_duplicates=skipped,
        errors=errors,
        job_status=refreshed.status,
        message=message,
    )

    # T-S02-007: сохраняем в idempotency cache для повторных запросов.
    if cache_key is not None:
        idempotency.set(cache_key, response)

    return response


@router.get(
    "/{setup_job_id}/documents",
    response_model=ListDocumentsResponse,
    summary="List source documents (T-S01-015)",
)
def list_documents(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_DOCUMENT_UPLOAD)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
) -> ListDocumentsResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal)

    include_paths = principal.has_permission(Permission.KB_PUBLISH)
    documents = [
        _to_doc_response(d, include_storage_path=include_paths)
        for d in registry.list_for_job(setup_job_id)
    ]
    return ListDocumentsResponse(
        setup_job_id=setup_job_id,
        documents=documents,
        count=len(documents),
    )


# Ссылка на SourceDocumentNotFoundError, чтобы не отдалять её от router'а.
_ = SourceDocumentNotFoundError


@router.get(
    "/{setup_job_id}/documents/{source_document_id}",
    response_model=SourceDocumentResponse,
    summary="Get source document metadata (T-S02-015)",
)
def get_document_metadata(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_DOCUMENT_UPLOAD)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
) -> SourceDocumentResponse:
    """T-S02-015: возвращает metadata одного документа (без binary content)."""
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    # Cross-job protection: документ должен принадлежать этому setup_job_id.
    if document.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source document {source_document_id!r} not in job {setup_job_id!r}",
        )

    include_paths = principal.has_permission(Permission.KB_PUBLISH)
    return _to_doc_response(document, include_storage_path=include_paths)


@router.delete(
    "/{setup_job_id}/documents/{source_document_id}",
    response_model=RemoveDocumentResponse,
    summary="Remove source document (T-S02-014)",
)
def delete_document(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    reason: str | None = Query(default=None, max_length=2000),
    principal: Principal = Depends(require_permission(Permission.KB_DOCUMENT_DELETE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    upload_svc: DocumentUploadService = Depends(get_upload_service),
) -> RemoveDocumentResponse:
    """T-S02-014: soft-delete документа.

    - Только если job в DRAFT/FILES_UPLOADED (иначе 409).
    - Идемпотентно: повторный DELETE возвращает тот же `status=removed`.
    - Cross-job protection: документ должен принадлежать этому setup_job_id.
    """
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="delete document from")

    try:
        removed = upload_svc.remove_document(
            setup_job_id=setup_job_id,
            source_document_id=source_document_id,
            actor_id=principal.user_id,
            reason=reason,
        )
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except JobNotAcceptingUploadsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return RemoveDocumentResponse(
        setup_job_id=setup_job_id,
        source_document_id=removed.source_document_id,
        status=removed.status.value,
        message=f"Document {removed.source_document_id} removed",
    )


@router.post(
    "/{setup_job_id}/run",
    response_model=RunPipelineResponse,
    summary="Run setup pipeline (T-S01-022)",
)
def run_pipeline(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    pipeline: SetupPipeline = Depends(get_pipeline),
) -> RunPipelineResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="run")

    if job.status == SetupJobStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload at least one document before running the pipeline",
        )

    try:
        result = pipeline.run(setup_job_id)
    except PipelineError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    message = None
    if result.final_status == SetupJobStatus.FAILED:
        message = "Pipeline failed — see errors[] for details"
    elif result.cards_review_required:
        message = (
            f"Pipeline completed; {result.cards_review_required} card(s) "
            "require human review (S4)"
        )
    elif result.final_status == SetupJobStatus.INDEXING:
        message = (
            f"Pipeline completed; indexed {result.chunks_indexed}/"
            f"{result.chunks_total} chunks"
        )
    else:
        message = "Pipeline completed successfully"

    vector_index_summary = None
    if result.vector_index is not None:
        vi = result.vector_index
        vector_index_summary = VectorIndexSummary(
            index_version=vi.index_version,
            status=vi.status.value,
            embedding_model=vi.embedding_model,
            chunks_count=vi.chunks_count,
            indexed_chunks_count=vi.indexed_chunks_count,
            failed_chunks_count=vi.failed_chunks_count,
            collection_names=list(vi.collection_names),
        )

    return RunPipelineResponse(
        setup_job_id=result.setup_job_id,
        final_status=result.final_status,
        documents_total=result.documents_total,
        documents_parsed=result.documents_parsed,
        documents_failed=result.documents_failed,
        sections_extracted=result.sections_extracted,
        cards_generated=result.cards_generated,
        cards_review_required=result.cards_review_required,
        cards_used_fallback=result.cards_used_fallback,
        cards_metadata_validated=result.cards_metadata_validated,
        validation_warnings=result.validation_warnings,
        validation_failed=result.validation_failed,
        cards_approved_auto=result.cards_approved_auto,
        chunks_total=result.chunks_total,
        chunks_indexed=result.chunks_indexed,
        chunks_failed=result.chunks_failed,
        vector_index=vector_index_summary,
        errors=result.errors,
        message=message,
    )


@router.get(
    "/{setup_job_id}/rag-cards",
    response_model=ListCardsResponse,
    summary="List RAG cards (T-S01-027)",
)
def list_rag_cards(
    setup_job_id: str = Path(..., min_length=1),
    card_status: str | None = Query(default=None, description="Filter by status"),
    doc_type: str | None = Query(default=None, description="Filter by doc_type"),
    confidence_level: str | None = Query(default=None, description="Filter by confidence"),
    include: str | None = Query(
        default=None,
        pattern=r"^body$",
        description="Set to 'body' to include full body_markdown",
    ),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> ListCardsResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal)

    records = card_registry.list_for_job(setup_job_id)

    if card_status:
        records = [r for r in records if r.card.status.value == card_status]
    if doc_type:
        records = [r for r in records if r.card.doc_type.value == doc_type]
    if confidence_level:
        records = [
            r
            for r in records
            if (r.card.confidence_level or "") == confidence_level
        ]

    include_body = include == "body"

    # Сортировка для UI: review_required → metadata_validated → approved → ...
    _order: dict[str, int] = {
        "review_required": 0,
        "metadata_validated": 1,
        "generated": 2,
        "approved": 3,
        "chunked": 4,
        "embedded": 5,
        "indexed": 6,
        "published": 7,
        "draft": 8,
        "deprecated": 9,
    }
    records.sort(key=lambda r: _order.get(r.card.status.value, 99))

    summaries = [
        RAGCardSummary(
            doc_id=r.card.doc_id,
            doc_type=r.card.doc_type.value,
            title=r.card.title,
            version=r.card.version,
            status=r.card.status.value,
            confidence_level=r.card.confidence_level,
            domain=[d.value for d in r.metadata.domain],
            phase=[p.value for p in r.metadata.phase],
            retrieval_tags=list(r.metadata.retrieval_tags),
            source_document_ids=list(r.card.source_document_ids),
            created_at=r.card.created_at,
            updated_at=r.card.updated_at,
            body_preview=(r.card.body_markdown[:500] if not include_body else None),
            body_markdown=r.card.body_markdown if include_body else None,
            history=list(r.history),
        )
        for r in records
    ]

    return ListCardsResponse(
        setup_job_id=setup_job_id,
        cards=summaries,
        count=len(summaries),
        filters={
            "status": card_status,
            "doc_type": doc_type,
            "confidence_level": confidence_level,
            "include": include,
        },
    )


@router.post(
    "/{setup_job_id}/rag-cards/{doc_id}/review",
    response_model=ReviewRAGCardResponse,
    summary="Review RAG card (T-S01-026)",
)
def review_rag_card(
    payload: ReviewRAGCardRequest,
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_CARD_REVIEW)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
    review_service: RAGCardReviewService = Depends(get_card_review),
) -> ReviewRAGCardResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="review")

    # Карточка должна принадлежать этому setup_job_id.
    try:
        existing = card_registry.get(doc_id)
    except CardNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if existing.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card {doc_id!r} not found in setup_job {setup_job_id!r}",
        )

    try:
        decision = ReviewDecision(payload.decision)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown decision: {payload.decision}",
        ) from exc

    try:
        if decision == ReviewDecision.APPROVE:
            updated = review_service.approve(
                doc_id=doc_id, reviewer_id=principal.user_id, comment=payload.comment
            )
        elif decision == ReviewDecision.REJECT:
            updated = review_service.reject(
                doc_id=doc_id, reviewer_id=principal.user_id, comment=payload.comment
            )
        elif decision == ReviewDecision.REGENERATE:
            updated = review_service.regenerate(
                doc_id=doc_id, reviewer_id=principal.user_id, comment=payload.comment
            )
        else:  # EDIT
            updated = review_service.edit(
                doc_id=doc_id,
                reviewer_id=principal.user_id,
                updated_title=payload.updated_title,
                updated_body_markdown=payload.updated_body_markdown,
                comment=payload.comment,
            )
    except InvalidEditPayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except InvalidReviewStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    new_doc_id = updated.card.doc_id if decision == ReviewDecision.EDIT else None
    return ReviewRAGCardResponse(
        setup_job_id=setup_job_id,
        decision=decision.value,
        affected_doc_id=doc_id,
        new_doc_id=new_doc_id,
        new_status=updated.card.status.value,
        message=f"Decision '{decision.value}' applied to {doc_id}",
    )


@router.post(
    "/{setup_job_id}/reindex",
    response_model=ReindexResponse,
    summary="Reindex approved cards (T-S01-034)",
)
def reindex_cards(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PUBLISH)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
    indexer: VectorIndexerService = Depends(get_vector_indexer),
) -> ReindexResponse:
    """Создаёт новую index_version без затрагивания active KB.

    Используется для:
    - повторной индексации после изменения карточек;
    - смены embedding-модели (требует новый index_version);
    - rebuild после Qdrant cleanup.
    """
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="reindex")

    # Собираем approved + indexed карточки.
    eligible_records = card_registry.list_for_job(
        setup_job_id,
        status_in=frozenset(
            {
                _CardStatus.APPROVED,
                _CardStatus.CHUNKED,
                _CardStatus.EMBEDDED,
                _CardStatus.INDEXED,
            }
        ),
    )
    if not eligible_records:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No approved cards to reindex; run pipeline or approve cards first",
        )

    pairs = [(r.card, r.metadata) for r in eligible_records]
    try:
        index_result = indexer.index_cards(pairs)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reindex failed: {type(exc).__name__}: {exc}",
        ) from exc

    if index_result.vector_index is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reindex returned no VectorIndex",
        )

    vi = index_result.vector_index
    return ReindexResponse(
        setup_job_id=setup_job_id,
        index_version=index_result.index_version,
        chunks_total=index_result.chunks_total,
        chunks_indexed=index_result.chunks_indexed,
        chunks_failed=index_result.chunks_failed,
        vector_index=VectorIndexSummary(
            index_version=vi.index_version,
            status=vi.status.value,
            embedding_model=vi.embedding_model,
            chunks_count=vi.chunks_count,
            indexed_chunks_count=vi.indexed_chunks_count,
            failed_chunks_count=vi.failed_chunks_count,
            collection_names=list(vi.collection_names),
        ),
        errors=index_result.errors,
        message=f"Reindexed {index_result.chunks_indexed}/{index_result.chunks_total} chunks",
    )


@router.post(
    "/{setup_job_id}/retrieval-tests",
    response_model=EvalReportResponse,
    summary="Run retrieval tests (T-S01-037)",
)
def run_retrieval_tests(
    payload: RunRetrievalTestsRequest,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    evaluation: RAGEvaluationService = Depends(get_evaluation_service),
) -> EvalReportResponse:
    """Запускает golden-set retrieval-tests; gate = mean recall@5 ≥ threshold."""
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="retrieval-tests")

    golden = [
        GoldenQuery(
            query=g.query,
            expected_doc_ids=list(g.expected_doc_ids),
            doc_types=list(g.doc_types) if g.doc_types else None,
            description=g.description,
        )
        for g in payload.golden_queries
    ]
    # threshold override (per-request) > evaluation_service default
    if payload.threshold_recall_at_5 is not None:
        from fe_bot.setup.evaluation.service import RAGEvaluationService as _Svc

        eval_service: RAGEvaluationService = _Svc(
            retrieval=evaluation._retrieval,
            threshold_recall_at_5=payload.threshold_recall_at_5,
        )
    else:
        eval_service = evaluation

    report = eval_service.evaluate(golden, top_k=payload.top_k)

    if job.status == SetupJobStatus.INDEXING:
        # job уже мог быть переведён или это повторный запуск — глотаем.
        with contextlib.suppress(InvalidTransitionError):
            orchestrator.advance(
                setup_job_id,
                SetupJobStatus.RETRIEVAL_TESTING,
                message=(
                    f"Retrieval tests: recall@{report.top_k}={report.mean_recall_at_k:.2f}"
                ),
                metrics={
                    "mean_recall_at_k": report.mean_recall_at_k,
                    "mean_precision_at_k": report.mean_precision_at_k,
                    "no_context_rate": report.no_context_rate,
                    "passed": report.passed,
                },
            )

    return EvalReportResponse(
        setup_job_id=setup_job_id,
        queries_total=report.queries_total,
        queries_errored=report.queries_errored,
        top_k=report.top_k,
        threshold_recall_at_5=report.threshold_recall_at_5,
        mean_recall_at_k=report.mean_recall_at_k,
        mean_precision_at_k=report.mean_precision_at_k,
        mean_reciprocal_rank=report.mean_reciprocal_rank,
        no_context_rate=report.no_context_rate,
        passed=report.passed,
        per_query=[
            PerQueryEvalDTO(
                query=p.query,
                expected_doc_ids=list(p.expected_doc_ids),
                retrieved_doc_ids=list(p.retrieved_doc_ids),
                recall_at_k=p.recall_at_k,
                precision_at_k=p.precision_at_k,
                reciprocal_rank=p.reciprocal_rank,
                is_no_context=p.is_no_context,
                error_message=p.error_message,
            )
            for p in report.per_query
        ],
        message=(
            f"Retrieval gate {'PASSED' if report.passed else 'FAILED'}: "
            f"recall@{report.top_k}={report.mean_recall_at_k:.2f}"
        ),
    )


@router.post(
    "/{setup_job_id}/publish",
    response_model=PublishKBResponse,
    summary="Publish KB (T-S01-039)",
)
def publish_kb(
    payload: PublishKBRequest,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PUBLISH)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
    vector_indexer: VectorIndexerService = Depends(get_vector_indexer),
    publish_service: KBPublishService = Depends(get_kb_publish_service),
    kb_repository: InMemoryKBRepository = Depends(get_kb_repository),
) -> PublishKBResponse:
    """Создаёт KB version, переводит lifecycle до ACTIVE."""
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="publish")

    # Gate: должен быть пройден retrieval-eval (если предоставлен).
    if payload.eval_report is not None and not payload.eval_report.passed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot publish KB: retrieval-eval gate not passed",
        )

    # Считаем approved + indexed карточки.
    approved_or_indexed = card_registry.list_for_job(
        setup_job_id,
        status_in=frozenset(
            {
                _CardStatus.APPROVED,
                _CardStatus.CHUNKED,
                _CardStatus.EMBEDDED,
                _CardStatus.INDEXED,
            }
        ),
    )
    if not approved_or_indexed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No approved cards to publish; complete review first",
        )

    # Извлекаем последний index_version из job.metrics или фолбэк на N/A.
    last_index_version = job.knowledge_base_version or "idx_unknown"
    # Считаем chunks через VectorIndexClient напрямую.
    index_client = vector_indexer._index_client
    chunk_count = sum(
        index_client.count(c) for c in index_client.list_collections()
    )

    # Lifecycle: DRAFT → TESTING → READY → ACTIVE.
    kb = publish_service.create_draft(
        setup_job_id=setup_job_id,
        index_version=last_index_version,
        rag_card_count=len(approved_or_indexed),
        chunk_count=chunk_count,
    )
    publish_service.mark_testing(kb.knowledge_base_version)
    publish_service.mark_ready(
        kb.knowledge_base_version,
        retrieval_test_report_id=(
            f"eval_{kb.knowledge_base_version}" if payload.eval_report else "no_eval"
        ),
    )
    try:
        active = publish_service.activate(
            kb.knowledge_base_version, published_by=principal.user_id
        )
    except PublishNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    # Транзитим job: → publishing → ready
    try:
        if job.status != SetupJobStatus.READY:
            orchestrator.advance(
                setup_job_id,
                SetupJobStatus.PUBLISHING,
                message=f"Publishing KB {active.knowledge_base_version}",
            )
            ready_job = orchestrator.advance(
                setup_job_id,
                SetupJobStatus.READY,
                message="KB published successfully",
                metrics={
                    "knowledge_base_version": active.knowledge_base_version,
                    "rag_card_count": active.rag_card_count,
                    "chunk_count": active.chunk_count,
                },
            )
            ready_job.knowledge_base_version = active.knowledge_base_version
    except InvalidTransitionError:
        pass

    # Промаркируем карточки как PUBLISHED.
    for rec in approved_or_indexed:
        current = card_registry.get(rec.card.doc_id).card
        if current.can_transition_to(_CardStatus.PUBLISHED):
            updated = current.model_copy(update={"status": _CardStatus.PUBLISHED})
            card_registry.update(
                rec.card.doc_id,
                card=updated,
                note=f"published with KB {active.knowledge_base_version}",
            )

    return PublishKBResponse(
        setup_job_id=setup_job_id,
        knowledge_base_version=active.knowledge_base_version,
        status=active.status.value,
        is_active=active.is_active,
        published_by=active.published_by,
        published_at=active.published_at,
        index_version=active.index_version,
        rag_card_count=active.rag_card_count,
        chunk_count=active.chunk_count,
        message=f"KB {active.knowledge_base_version} activated",
    )


@router.get(
    "/{setup_job_id}/report",
    response_model=ProcessingReportResponse,
    summary="Get processing report (T-S01-039)",
)
def get_report(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_REPORT_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
    source_registry: InMemorySourceRegistry = Depends(get_source_registry),
    kb_repository: InMemoryKBRepository = Depends(get_kb_repository),
) -> ProcessingReportResponse:
    """Возвращает итоговую сводку по job (documents + cards + KB + eval)."""
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    _check_job_access(job, principal, action="report")

    documents = source_registry.list_for_job(setup_job_id)
    cards = card_registry.list_for_job(setup_job_id)
    by_status: dict[str, int] = {}
    for rec in cards:
        by_status[rec.card.status.value] = by_status.get(rec.card.status.value, 0) + 1
    cards_approved = (
        by_status.get("approved", 0)
        + by_status.get("chunked", 0)
        + by_status.get("embedded", 0)
        + by_status.get("indexed", 0)
        + by_status.get("published", 0)
    )

    # KB info
    active_kb = kb_repository.get_active_for_setup_job(setup_job_id)
    all_kbs = kb_repository.list_for_setup_job(setup_job_id)
    if active_kb is None and all_kbs:
        # Возьмём последнюю.
        active_kb = max(all_kbs, key=lambda k: k.knowledge_base_version)

    return ProcessingReportResponse(
        setup_job_id=setup_job_id,
        status=job.status,
        project_name=job.project_name,
        user_id=job.user_id,
        progress_percent=job.progress_percent,
        error_count=job.error_count,
        warning_count=job.warning_count,
        documents_count=len(documents),
        cards_count=len(cards),
        cards_approved=cards_approved,
        cards_review_required=by_status.get("review_required", 0),
        cards_deprecated=by_status.get("deprecated", 0),
        knowledge_base_version=(
            active_kb.knowledge_base_version if active_kb else None
        ),
        knowledge_base_status=active_kb.status.value if active_kb else None,
        knowledge_base_is_active=bool(active_kb and active_kb.is_active),
        chunks_indexed=active_kb.chunk_count if active_kb else 0,
        index_version=active_kb.index_version if active_kb else None,
        eval_passed=(
            (active_kb.status == KBStatus.ACTIVE) if active_kb else None
        ),
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


# Утилитарный endpoint, не из плана — на случай нужды smoke-проверки.
@router.get("/_health", summary="Setup module healthcheck", include_in_schema=False)
def healthcheck() -> dict[str, str | int | SetupJobStatus]:
    return {"status": "ok", "endpoints": len(router.routes)}
