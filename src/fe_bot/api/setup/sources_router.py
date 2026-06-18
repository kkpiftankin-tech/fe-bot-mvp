"""SETUP-03 Source Registry endpoints (T-S03-012..018).

7 endpoints под /api/v1/setup/{setup_job_id}/sources:
- GET    /sources                          — paginated list
- GET    /sources/{src_id}                  — детали + counters
- GET    /sources/{src_id}/status-history
- GET    /sources/{src_id}/processing-log
- GET    /sources/{src_id}/lineage
- PATCH  /sources/{src_id}/metadata        — user metadata only
- DELETE /sources/{src_id}                  — soft-delete

Auth (T-S03-016): использует kb.source.* permissions family.
- KB_SOURCE_LIST для list
- KB_SOURCE_READ для single GET и status-history
- KB_SOURCE_LINEAGE_READ для lineage
- KB_SOURCE_LOG_READ для processing-log
- KB_SOURCE_METADATA_UPDATE для PATCH metadata
- KB_SOURCE_REMOVE для DELETE
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError
from schemas.setup.lineage import LineageCounters
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep
from schemas.setup.rag_setup_job import RAGSetupJob
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus
from schemas.setup.source_document_metadata import (
    SystemMetadataReadOnlyError,
    UpdateSourceMetadataRequest,
)

from fe_bot.api.dependencies import (
    get_lineage_repo,
    get_orchestrator,
    get_processing_log_repo,
    get_source_lifecycle,
    get_source_registry,
    get_status_history_repo,
    get_upload_service,
    require_permission,
)
from fe_bot.api.setup.sources_dto import (
    LineageRelationDTO,
    LineageResponse,
    ListSourcesResponse,
    PaginationDTO,
    PatchSourceMetadataResponse,
    ProcessingLogResponse,
    RemoveSourceResponse,
    RetrySourceResponse,
    SourceDocumentDetailsDTO,
    SourceDocumentListItemDTO,
    StatusHistoryEntryDTO,
    StatusHistoryResponse,
    to_processing_log_dto,
    to_status_history_dto,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.repository import JobNotFoundError
from fe_bot.setup.source_registry.lifecycle import (
    InvalidStatusTransitionError,
    SourceLifecycleService,
)
from fe_bot.setup.source_registry.lineage import (
    InMemoryLineageRepository,
    LineageTargetType,
)
from fe_bot.setup.source_registry.processing_log import (
    InMemoryProcessingLogRepository,
)
from fe_bot.setup.source_registry.service import (
    InMemorySourceRegistry,
    SourceDocumentNotFoundError,
)
from fe_bot.setup.source_registry.status_history import (
    InMemoryStatusHistoryRepository,
)
from fe_bot.setup.upload.service import (
    DocumentUploadService,
    JobNotAcceptingUploadsError,
)

router = APIRouter(prefix="/api/v1/setup", tags=["sources"])

# Cross-job: kb_admin/admin/auditor могут читать чужие документы; user — только свои.
_CROSS_JOB_PERMISSIONS = (Permission.KB_PUBLISH, Permission.KB_CARD_REVIEW)


def _check_job_access(job: RAGSetupJob, principal: Principal) -> None:
    if job.user_id == principal.user_id:
        return
    if any(principal.has_permission(p) for p in _CROSS_JOB_PERMISSIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot read sources of job owned by another user",
    )


def _ensure_document_in_job(document: SourceDocument, setup_job_id: str) -> None:
    """Cross-job protection — нельзя видеть документ из чужого job по id."""
    if document.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source document {document.source_document_id!r} not in job {setup_job_id!r}",
        )


def _paginate[T](items: list[T], page: int, page_size: int) -> tuple[list[T], PaginationDTO]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], PaginationDTO(page=page, page_size=page_size, total=total)


_SORT_KEYS = {"filename", "uploaded_at", "size_bytes", "status"}


def _apply_sort(items: list[SourceDocument], sort: str) -> list[SourceDocument]:
    """Сортировка по `field:asc|desc`. Поддержанные поля в _SORT_KEYS."""
    if ":" not in sort:
        field, direction = sort, "asc"
    else:
        field, direction = sort.split(":", 1)
    if field not in _SORT_KEYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported sort field: {field!r}",
        )
    reverse = direction == "desc"
    return sorted(items, key=lambda d: getattr(d, field), reverse=reverse)


def _build_list_item(doc: SourceDocument, counters: LineageCounters) -> SourceDocumentListItemDTO:
    return SourceDocumentListItemDTO(
        source_document_id=doc.source_document_id,
        setup_job_id=doc.setup_job_id,
        filename=doc.filename,
        document_kind=doc.document_kind.value if doc.document_kind else None,
        content_type=doc.content_type,
        size_bytes=doc.size_bytes,
        checksum_short=doc.checksum[:12],
        status=doc.status,
        uploaded_by=doc.uploaded_by,
        uploaded_at=doc.uploaded_at,
        parsed_sections_count=counters.parsed_sections_count,
        rag_cards_count=counters.rag_cards_count,
        chunks_count=counters.chunks_count,
        last_error=doc.error_message,
    )


# ============================================================
# T-S03-012: GET /sources (list)
# ============================================================


@router.get(
    "/{setup_job_id}/sources",
    response_model=ListSourcesResponse,
    summary="List source documents (T-S03-012)",
)
def list_sources(
    setup_job_id: str = Path(..., min_length=1),
    status_filter: list[SourceDocumentStatus] | None = Query(default=None, alias="status"),
    document_kind: str | None = Query(default=None, max_length=50),
    content_type: str | None = Query(default=None, max_length=100),
    owner: str | None = Query(default=None, max_length=128),
    has_errors: bool | None = Query(default=None),
    has_rag_cards: bool | None = Query(default=None),
    include_removed: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="uploaded_at:desc"),
    principal: Principal = Depends(require_permission(Permission.KB_SOURCE_LIST)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    lineage: InMemoryLineageRepository = Depends(get_lineage_repo),
) -> ListSourcesResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    documents = list(registry.list_for_job(setup_job_id))
    if not include_removed:
        documents = [d for d in documents if d.status != SourceDocumentStatus.REMOVED]

    if status_filter:
        wanted = set(status_filter)
        documents = [d for d in documents if d.status in wanted]
    if document_kind:
        documents = [
            d for d in documents if d.document_kind and d.document_kind.value == document_kind
        ]
    if content_type:
        documents = [d for d in documents if d.content_type == content_type]
    if owner:
        documents = [d for d in documents if d.uploaded_by == owner]
    if has_errors is not None:
        documents = [d for d in documents if bool(d.error_message) is has_errors]

    documents = _apply_sort(documents, sort)

    if has_rag_cards is not None:
        filtered: list[SourceDocument] = []
        for d in documents:
            counters = lineage.counters(d.source_document_id)
            if (counters.rag_cards_count > 0) is has_rag_cards:
                filtered.append(d)
        documents = filtered

    paged, pagination = _paginate(documents, page, page_size)

    items = [_build_list_item(d, lineage.counters(d.source_document_id)) for d in paged]
    return ListSourcesResponse(setup_job_id=setup_job_id, items=items, pagination=pagination)


# ============================================================
# T-S03-013: GET /sources/{src_id}
# ============================================================


@router.get(
    "/{setup_job_id}/sources/{source_document_id}",
    response_model=SourceDocumentDetailsDTO,
    summary="Get source document details (T-S03-013)",
)
def get_source_details(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SOURCE_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    lineage: InMemoryLineageRepository = Depends(get_lineage_repo),
    history: InMemoryStatusHistoryRepository = Depends(get_status_history_repo),
) -> SourceDocumentDetailsDTO:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _ensure_document_in_job(document, setup_job_id)

    include_paths = principal.has_permission(Permission.KB_PUBLISH)
    user_meta = document.metadata.get("user", {}) or {}
    system_meta = {k: v for k, v in document.metadata.items() if k != "user"}
    latest = history.latest_for_document(source_document_id)
    last_change: datetime | None = latest.changed_at if latest else None
    return SourceDocumentDetailsDTO(
        source_document_id=document.source_document_id,
        setup_job_id=document.setup_job_id,
        filename=document.filename,
        original_filename=document.filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        checksum=document.checksum,
        storage_path=document.storage_path if include_paths else None,
        status=document.status,
        document_kind=document.document_kind.value if document.document_kind else None,
        detected_language=document.detected_language,
        uploaded_by=document.uploaded_by,
        uploaded_at=document.uploaded_at,
        parsed_at=document.parsed_at,
        error_message=document.error_message,
        user_metadata=user_meta if isinstance(user_meta, dict) else {},
        system_metadata=system_meta,
        counters=lineage.counters(source_document_id),
        last_status_change=last_change,
    )


# ============================================================
# T-S03-014: GET /sources/{src_id}/status-history
# ============================================================


@router.get(
    "/{setup_job_id}/sources/{source_document_id}/status-history",
    response_model=StatusHistoryResponse,
    summary="Get source status history (T-S03-014)",
)
def get_status_history(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    since: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_permission(Permission.KB_SOURCE_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    history: InMemoryStatusHistoryRepository = Depends(get_status_history_repo),
) -> StatusHistoryResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _ensure_document_in_job(document, setup_job_id)

    entries = history.list_for_document(source_document_id)
    if since is not None:
        entries = [e for e in entries if e.changed_at >= since]

    paged_entries, pagination = _paginate(entries, page, page_size)
    items: list[StatusHistoryEntryDTO] = [to_status_history_dto(e) for e in paged_entries]
    return StatusHistoryResponse(
        source_document_id=source_document_id,
        items=items,
        pagination=pagination,
    )


# ============================================================
# T-S03-015: GET /sources/{src_id}/processing-log + /lineage
# ============================================================


@router.get(
    "/{setup_job_id}/sources/{source_document_id}/processing-log",
    response_model=ProcessingLogResponse,
    summary="Get source processing log (T-S03-015)",
)
def get_processing_log(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    step: ProcessingLogStep | None = Query(default=None),
    level: ProcessingLogLevel | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_permission(Permission.KB_SOURCE_LOG_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    processing_log: InMemoryProcessingLogRepository = Depends(get_processing_log_repo),
) -> ProcessingLogResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _ensure_document_in_job(document, setup_job_id)

    entries = processing_log.list_for_document(source_document_id, step=step, level=level)
    paged, pagination = _paginate(entries, page, page_size)
    return ProcessingLogResponse(
        source_document_id=source_document_id,
        items=[to_processing_log_dto(e) for e in paged],
        pagination=pagination,
    )


@router.get(
    "/{setup_job_id}/sources/{source_document_id}/lineage",
    response_model=LineageResponse,
    summary="Get source lineage (T-S03-015)",
)
def get_lineage(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    target_type: LineageTargetType | None = Query(default=None),
    principal: Principal = Depends(require_permission(Permission.KB_SOURCE_LINEAGE_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    lineage: InMemoryLineageRepository = Depends(get_lineage_repo),
) -> LineageResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _ensure_document_in_job(document, setup_job_id)

    relations = lineage.list_for_source(source_document_id, target_type=target_type)
    counters = lineage.counters(source_document_id)
    return LineageResponse(
        source_document_id=source_document_id,
        relations=[
            LineageRelationDTO(
                lineage_id=r.lineage_id,
                source_document_id=r.source_document_id,
                target_type=r.target_type.value,
                target_id=r.target_id,
                relation_type=r.relation_type.value,
                created_by_service=r.created_by_service,
                event_id=r.event_id,
                created_at=r.created_at,
                metadata=r.metadata,
            )
            for r in relations
        ],
        counters=counters,
    )


# ============================================================
# T-S03-017: PATCH /sources/{src_id}/metadata
# ============================================================


@router.patch(
    "/{setup_job_id}/sources/{source_document_id}/metadata",
    response_model=PatchSourceMetadataResponse,
    summary="Update user metadata (T-S03-017)",
)
def patch_source_metadata(
    payload: UpdateSourceMetadataRequest,
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    event_id: str | None = Query(default=None, max_length=128),
    principal: Principal = Depends(require_permission(Permission.KB_SOURCE_METADATA_UPDATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    lifecycle: SourceLifecycleService = Depends(get_source_lifecycle),
) -> PatchSourceMetadataResponse:
    """T-S03-017: PATCH user metadata (tags, description, owner_note, custom_labels).

    Protected fields (checksum, storage_path, status, etc.) защищены схемой
    UpdateSourceMetadataRequest (extra=forbid) + SystemMetadataReadOnlyError.
    """
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _ensure_document_in_job(document, setup_job_id)

    try:
        updated = lifecycle.update_user_metadata(
            source_document_id=source_document_id,
            patch=payload,
            updated_by=principal.user_id,
            event_id=event_id,
        )
    except SystemMetadataReadOnlyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "SYSTEM_METADATA_READ_ONLY",
                "message": str(exc),
                "field": exc.field_name,
            },
        ) from exc
    except ValidationError as exc:
        # Sanitize/length validators в SourceDocumentUserMetadata.
        # errors() содержит ctx с raw exception — отфильтруем для JSON-safety.
        safe_errors = [
            {k: v for k, v in err.items() if k != "ctx"} for err in exc.errors(include_url=False)
        ]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_METADATA_PATCH",
                "message": "Validation failed",
                "errors": safe_errors,
            },
        ) from exc

    user_meta = updated.metadata.get("user", {}) or {}
    return PatchSourceMetadataResponse(
        source_document_id=updated.source_document_id,
        setup_job_id=updated.setup_job_id,
        user_metadata=user_meta if isinstance(user_meta, dict) else {},
        updated_at=datetime.now(updated.uploaded_at.tzinfo),
        message=f"Metadata updated for {source_document_id}",
    )


# ============================================================
# T-S03-018: DELETE /sources/{src_id}
# ============================================================


@router.delete(
    "/{setup_job_id}/sources/{source_document_id}",
    response_model=RemoveSourceResponse,
    summary="Remove source document (T-S03-018)",
)
def delete_source(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    reason: str | None = Query(default=None, max_length=2000),
    principal: Principal = Depends(require_permission(Permission.KB_SOURCE_REMOVE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    upload_svc: DocumentUploadService = Depends(get_upload_service),
) -> RemoveSourceResponse:
    """T-S03-018: soft-delete документа.

    Дополнительно к SETUP-02 DELETE: блокирует удаление PUBLISHED документа
    без admin override (AC-29 — DOCUMENT_ALREADY_PUBLISHED).
    """
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _ensure_document_in_job(document, setup_job_id)

    # AC-29: документ в published KB нельзя удалить без admin (KB_PUBLISH).
    if document.status == SourceDocumentStatus.PUBLISHED and not principal.has_permission(
        Permission.KB_PUBLISH
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "DOCUMENT_ALREADY_PUBLISHED",
                "message": (
                    f"Document {source_document_id} is published — admin override required"
                ),
            },
        )

    try:
        removed = upload_svc.remove_document(
            setup_job_id=setup_job_id,
            source_document_id=source_document_id,
            actor_id=principal.user_id,
            reason=reason,
        )
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except JobNotAcceptingUploadsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "DOCUMENT_NOT_REMOVABLE",
                "message": str(exc),
            },
        ) from exc

    return RemoveSourceResponse(
        source_document_id=removed.source_document_id,
        setup_job_id=setup_job_id,
        status=removed.status.value,
        message=f"Source document {removed.source_document_id} removed",
    )


# ============================================================
# T-S03-021: POST /sources/{src_id}/retry
# ============================================================


@router.post(
    "/{setup_job_id}/sources/{source_document_id}/retry",
    response_model=RetrySourceResponse,
    summary="Retry processing from failed step (T-S03-021)",
)
def retry_source(
    setup_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    from_step: ProcessingLogStep = Query(default=ProcessingLogStep.PARSING),
    event_id: str | None = Query(default=None, max_length=128),
    reason: str | None = Query(default=None, max_length=2000),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    registry: InMemorySourceRegistry = Depends(get_source_registry),
    lifecycle: SourceLifecycleService = Depends(get_source_lifecycle),
) -> RetrySourceResponse:
    """T-S03-021: ручной retry из PARSE_FAILED/PROCESSING_FAILED.

    Закрывает T-S02-016 (был deferred в SETUP-02).
    """
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)

    try:
        document = registry.get(source_document_id)
    except SourceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _ensure_document_in_job(document, setup_job_id)

    effective_event_id = event_id or f"retry:{source_document_id}:{from_step.value}"
    try:
        updated = lifecycle.retry_processing(
            source_document_id=source_document_id,
            from_step=from_step,
            event_id=effective_event_id,
            actor_id=principal.user_id,
            reason=reason,
        )
    except InvalidStatusTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "INVALID_RETRY_STATE",
                "message": str(exc),
                "current_status": (exc.old_status.value if exc.old_status else None),
            },
        ) from exc

    return RetrySourceResponse(
        source_document_id=updated.source_document_id,
        setup_job_id=updated.setup_job_id,
        status=updated.status.value,
        from_step=from_step.value,
        message=f"Retry triggered from step {from_step.value}",
    )
