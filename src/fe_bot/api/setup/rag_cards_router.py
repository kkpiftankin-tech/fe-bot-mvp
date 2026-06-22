"""SETUP-05 RAG Cards endpoints (T-S05-028..032).

7 endpoints под /api/v1/setup/{setup_job_id}/...:

- POST   /rag-cards/generate                              — создать generation job
- POST   /rag-card-generation-jobs/{job_id}/run           — синхронный запуск
- GET    /rag-card-generation-jobs/{job_id}               — статус job
- GET    /rag-card-generation-jobs/{job_id}/report        — финальный report
- GET    /rag-cards                                       — список карточек
- GET    /rag-cards/{doc_id}                              — детали карточки
- GET    /rag-cards/{doc_id}/preview                      — preview
- POST   /rag-cards/{doc_id}/regenerate                   — регенерация
- POST   /rag-card-generation-jobs/{job_id}/cancel        — отмена
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.setup.rag_card_generation_job import (
    InvalidRAGCardJobTransitionError,
    RAGCardGenerationErrorCode,
    RAGCardGenerationJob,
    RAGCardGenerationJobStatus,
)
from schemas.setup.rag_setup_job import RAGSetupJob

# Use dependency factory directly to avoid circular import with InMemoryRAGCardRegistry.
from fe_bot.api.dependencies import _card_registry as _card_registry_default  # noqa: E402
from fe_bot.api.dependencies import (
    get_audit_service,
    get_card_generation_report_repo,
    get_orchestrator,
    get_rag_card_job_repo,
    get_rag_card_orchestrator,
    get_rag_card_source_link_repo,
    require_permission,
)
from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.api.setup.rag_cards_dto import (
    CancelRAGCardJobResponse,
    CardGenerationSummaryDTO,
    GenerateRAGCardsRequest,
    PaginationDTO,
    RAGCardDetailsDTO,
    RAGCardGenerationJobResponse,
    RAGCardGenerationReportResponse,
    RAGCardListItemDTO,
    RAGCardListResponse,
    RAGCardPreviewDTO,
    RAGCardSourceTraceDTO,
    RegenerateRAGCardRequest,
    RegenerateRAGCardResponse,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.rag_card_generation.job_repository import (
    InMemoryRAGCardGenerationJobRepository,
    RAGCardGenerationJobNotFoundError,
)
from fe_bot.setup.rag_card_generation.orchestrator import (
    NoSectionsReadyError,
    RAGCardGenerationAlreadyRunningError,
    RAGCardGenerationOrchestrator,
)
from fe_bot.setup.rag_card_generation.report_repository import (
    InMemoryCardGenerationReportRepository,
)
from fe_bot.setup.rag_card_generation.source_link_repository import (
    InMemoryRAGCardSourceLinkRepository,
)
from fe_bot.setup.repository import JobNotFoundError

router = APIRouter(prefix="/api/v1/setup", tags=["rag-cards"])

_CROSS_JOB_PERMISSIONS = (Permission.KB_PUBLISH, Permission.KB_CARD_REVIEW)


def get_card_registry() -> InMemoryRAGCardRegistry:
    return _card_registry_default


# ============================================================
# Helpers
# ============================================================


def _check_job_access(job: RAGSetupJob, principal: Principal) -> None:
    if job.user_id == principal.user_id:
        return
    if any(principal.has_permission(p) for p in _CROSS_JOB_PERMISSIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot access RAG cards of another user's setup job",
    )


def _load_setup_job(
    *,
    orchestrator: SetupOrchestrator,
    setup_job_id: str,
    principal: Principal,
) -> RAGSetupJob:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _check_job_access(job, principal)
    return job


def _load_gen_job(
    *,
    job_repo: InMemoryRAGCardGenerationJobRepository,
    generation_job_id: str,
    setup_job_id: str,
) -> RAGCardGenerationJob:
    try:
        job = job_repo.get(generation_job_id)
    except RAGCardGenerationJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if job.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"RAGCardGenerationJob {generation_job_id!r} does not belong "
                f"to setup_job {setup_job_id!r}"
            ),
        )
    return job


def _job_response(job: RAGCardGenerationJob) -> RAGCardGenerationJobResponse:
    return RAGCardGenerationJobResponse(
        generation_job_id=job.generation_job_id,
        setup_job_id=job.setup_job_id,
        requested_by=job.requested_by,
        status=job.status,
        total_sections=job.total_sections,
        processed_sections=job.processed_sections,
        generated_cards=job.generated_cards,
        failed_sections=job.failed_sections,
        review_required_cards=job.review_required_cards,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_code=job.error_code,
        error_message=job.error_message,
        config=job.config,
    )


def _card_to_list_item(card: RAGCard) -> RAGCardListItemDTO:
    retrieval_tags = card.front_matter.get("retrieval_tags") or []
    if not isinstance(retrieval_tags, list):
        retrieval_tags = []
    return RAGCardListItemDTO(
        doc_id=card.doc_id,
        setup_job_id=card.setup_job_id or "",
        card_version=card.card_version,
        doc_type=card.doc_type.value,
        title=card.title,
        status=card.status.value,
        confidence_level=card.confidence_level,
        primary_source_section_id=card.primary_source_section_id,
        source_document_ids=list(card.source_document_ids),
        retrieval_tags=[str(t) for t in retrieval_tags],
        created_at=card.created_at,
        updated_at=card.updated_at,
        review_required_reason=card.review_required_reason,
    )


def _paginate[T](items: list[T], page: int, page_size: int) -> tuple[list[T], PaginationDTO]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], PaginationDTO(page=page, page_size=page_size, total=total)


# ============================================================
# T-S05-028: POST /rag-cards/generate
# ============================================================


@router.post(
    "/{setup_job_id}/rag-cards/generate",
    response_model=RAGCardGenerationJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create RAG card generation job (T-S05-028)",
)
def create_rag_card_generation_job(
    payload: GenerateRAGCardsRequest,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_GENERATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    rag_orchestrator: RAGCardGenerationOrchestrator = Depends(get_rag_card_orchestrator),
) -> RAGCardGenerationJobResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    config = {
        "generation_mode": payload.generation_mode,
        "ontology_version": payload.ontology_version,
        "metadata_schema_version": payload.metadata_schema_version,
        "prompt_template_version": payload.prompt_template_version,
        "llm_model": payload.llm_model,
        "options": payload.options.model_dump(),
    }
    if payload.generation_request_id:
        config["generation_request_id"] = payload.generation_request_id

    try:
        job = rag_orchestrator.create_job(
            setup_job_id=setup_job_id,
            requested_by=principal.user_id,
            section_ids=payload.section_ids,
            config=config,
        )
    except RAGCardGenerationAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": (
                    RAGCardGenerationErrorCode.RAG_CARD_GENERATION_ALREADY_RUNNING.value
                ),
                "message": str(exc),
                "active_generation_job_id": exc.active_generation_job_id,
            },
        ) from exc
    except NoSectionsReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": (
                    RAGCardGenerationErrorCode.NO_SECTIONS_READY_FOR_CARD_GENERATION.value
                ),
                "message": str(exc),
            },
        ) from exc
    return _job_response(job)


# ============================================================
# T-S05-028: POST /rag-card-generation-jobs/{job_id}/run
# ============================================================


@router.post(
    "/{setup_job_id}/rag-card-generation-jobs/{generation_job_id}/run",
    response_model=RAGCardGenerationJobResponse,
    summary="Run RAG card generation job synchronously (T-S05-028)",
)
def run_rag_card_generation_job(
    setup_job_id: str = Path(..., min_length=1),
    generation_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_GENERATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    rag_orchestrator: RAGCardGenerationOrchestrator = Depends(get_rag_card_orchestrator),
    job_repo: InMemoryRAGCardGenerationJobRepository = Depends(get_rag_card_job_repo),
) -> RAGCardGenerationJobResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_gen_job(
        job_repo=job_repo,
        generation_job_id=generation_job_id,
        setup_job_id=setup_job_id,
    )
    if job.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "RAG_CARD_GENERATION_JOB_TERMINAL",
                "message": f"Job is in terminal state {job.status.value}",
                "current_status": job.status.value,
            },
        )
    final = rag_orchestrator.run(generation_job_id)
    return _job_response(final)


# ============================================================
# T-S05-028: GET /rag-card-generation-jobs/{job_id}
# ============================================================


@router.get(
    "/{setup_job_id}/rag-card-generation-jobs/{generation_job_id}",
    response_model=RAGCardGenerationJobResponse,
    summary="Get RAG card generation job status (T-S05-028)",
)
def get_rag_card_generation_job(
    setup_job_id: str = Path(..., min_length=1),
    generation_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    job_repo: InMemoryRAGCardGenerationJobRepository = Depends(get_rag_card_job_repo),
) -> RAGCardGenerationJobResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_gen_job(
        job_repo=job_repo,
        generation_job_id=generation_job_id,
        setup_job_id=setup_job_id,
    )
    return _job_response(job)


@router.get(
    "/{setup_job_id}/rag-card-generation-jobs/{generation_job_id}/report",
    response_model=RAGCardGenerationReportResponse,
    summary="Get RAG card generation job report",
)
def get_rag_card_generation_report(
    setup_job_id: str = Path(..., min_length=1),
    generation_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    job_repo: InMemoryRAGCardGenerationJobRepository = Depends(get_rag_card_job_repo),
    report_repo: InMemoryCardGenerationReportRepository = Depends(get_card_generation_report_repo),
) -> RAGCardGenerationReportResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    _load_gen_job(
        job_repo=job_repo,
        generation_job_id=generation_job_id,
        setup_job_id=setup_job_id,
    )
    report = report_repo.get_for_job(generation_job_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"No report yet for generation_job_id={generation_job_id!r}",
        )
    return RAGCardGenerationReportResponse(
        generation_report_id=report.generation_report_id,
        generation_job_id=report.generation_job_id,
        status=report.status,
        summary=CardGenerationSummaryDTO(
            total_sections=report.summary.total_sections,
            processed_sections=report.summary.processed_sections,
            generated_cards=report.summary.generated_cards,
            failed_sections=report.summary.failed_sections,
            review_required_cards=report.summary.review_required_cards,
            cards_by_type=dict(report.summary.cards_by_type),
        ),
        errors=list(report.errors),
        warnings=list(report.warnings),
        created_at=report.created_at,
    )


# ============================================================
# T-S05-029: GET /rag-cards-catalog (filtered list)
# Note: legacy endpoint GET /rag-cards уже существует в setup_router (SETUP-01)
# и обслуживает базовый list. Новый ``/rag-cards-catalog`` добавляет SETUP-05
# фильтры (confidence_level, source_document_id) и pagination.
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards-catalog",
    response_model=RAGCardListResponse,
    summary="List RAG cards with SETUP-05 filters and pagination (T-S05-029)",
)
def list_rag_cards_catalog(
    setup_job_id: str = Path(..., min_length=1),
    doc_type: str | None = Query(default=None, min_length=1),
    status_filter: CardStatus | None = Query(default=None, alias="status"),
    confidence_level: str | None = Query(
        default=None,
        pattern=r"^(high|medium|low)$",
    ),
    source_document_id: str | None = Query(default=None, min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> RAGCardListResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    cards = card_registry.list_for_setup_job(
        setup_job_id,
        status=status_filter,
        confidence_level=confidence_level,
        source_document_id=source_document_id,
    )
    if doc_type is not None:
        cards = [c for c in cards if c.doc_type.value == doc_type]
    paged, pagination = _paginate(cards, page, page_size)
    return RAGCardListResponse(
        setup_job_id=setup_job_id,
        items=[_card_to_list_item(c) for c in paged],
        pagination=pagination,
    )


# ============================================================
# T-S05-029: GET /rag-cards/{doc_id} (details)
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards/{doc_id}",
    response_model=RAGCardDetailsDTO,
    summary="Get RAG card details (T-S05-029)",
)
def get_rag_card_details(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    version: str | None = Query(default=None),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> RAGCardDetailsDTO:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    try:
        if version is not None:
            card = card_registry.get_version(doc_id, version)
        else:
            latest = card_registry.latest_version(doc_id)
            if latest is None:
                raise CardNotFoundError(doc_id)
            card = latest
    except CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Cross-job isolation.
    if card.setup_job_id and card.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=404,
            detail=f"RAG card {doc_id!r} does not belong to setup_job {setup_job_id!r}",
        )

    versions = card_registry.list_versions(doc_id)
    return RAGCardDetailsDTO(
        doc_id=card.doc_id,
        setup_job_id=card.setup_job_id or "",
        card_version=card.card_version,
        doc_type=card.doc_type.value,
        title=card.title,
        status=card.status.value,
        confidence_level=card.confidence_level,
        front_matter=dict(card.front_matter),
        body_markdown=card.body_markdown,
        source_document_ids=list(card.source_document_ids),
        source_section_ids=list(card.source_section_ids),
        review_required_reason=card.review_required_reason,
        error_code=card.error_code,
        error_message=card.error_message,
        created_at=card.created_at,
        updated_at=card.updated_at,
        markdown_artifact_id=card.markdown_artifact_id,
        available_versions=versions,
    )


# ============================================================
# T-S05-029: GET /rag-cards/{doc_id}/preview
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards/{doc_id}/preview",
    response_model=RAGCardPreviewDTO,
    summary="Get RAG card preview (T-S05-029)",
)
def get_rag_card_preview(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    version: str | None = Query(default=None),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_PREVIEW)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
    source_link_repo: InMemoryRAGCardSourceLinkRepository = Depends(get_rag_card_source_link_repo),
) -> RAGCardPreviewDTO:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    try:
        if version is not None:
            card = card_registry.get_version(doc_id, version)
        else:
            latest = card_registry.latest_version(doc_id)
            if latest is None:
                raise CardNotFoundError(doc_id)
            card = latest
    except CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if card.setup_job_id and card.setup_job_id != setup_job_id:
        raise HTTPException(status_code=404, detail="Card not in this setup_job")

    links = source_link_repo.list_for_card(card.doc_id, card.card_version)
    return RAGCardPreviewDTO(
        doc_id=card.doc_id,
        card_version=card.card_version,
        doc_type=card.doc_type.value,
        title=card.title,
        status=card.status.value,
        confidence_level=card.confidence_level,
        front_matter=dict(card.front_matter),
        body_markdown=card.body_markdown,
        source_trace=[
            RAGCardSourceTraceDTO(
                source_link_id=link.source_link_id,
                source_document_id=link.source_document_id,
                source_section_id=link.source_section_id,
                relation_type=link.relation_type.value,
            )
            for link in links
        ],
    )


# ============================================================
# T-S05-030: POST /rag-cards/{doc_id}/regenerate
# ============================================================


@router.post(
    "/{setup_job_id}/rag-cards/{doc_id}/regenerate",
    response_model=RegenerateRAGCardResponse,
    summary="Regenerate RAG card (T-S05-030)",
)
def regenerate_rag_card(
    payload: RegenerateRAGCardRequest,
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_REGENERATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    rag_orchestrator: RAGCardGenerationOrchestrator = Depends(get_rag_card_orchestrator),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
    audit_service: AuditService = Depends(get_audit_service),
) -> RegenerateRAGCardResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    # Найти существующую карточку чтобы взять primary_source_section_id.
    latest = card_registry.latest_version(doc_id)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"RAG card not found: {doc_id}")
    if latest.setup_job_id and latest.setup_job_id != setup_job_id:
        raise HTTPException(status_code=404, detail="Card not in this setup_job")
    if not latest.primary_source_section_id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Card {doc_id} has no primary_source_section_id, "
                "cannot regenerate via single-section job"
            ),
        )

    # MVP: создать новый generation_job на одну секцию.
    try:
        job = rag_orchestrator.create_job(
            setup_job_id=setup_job_id,
            requested_by=principal.user_id,
            section_ids=[latest.primary_source_section_id],
            config={
                "generation_mode": "llm",
                "regenerate_of": doc_id,
                "regenerate_reason": payload.reason,
                "regenerate_request_id": payload.regenerate_request_id,
            },
        )
    except RAGCardGenerationAlreadyRunningError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": (
                    RAGCardGenerationErrorCode.RAG_CARD_GENERATION_ALREADY_RUNNING.value
                ),
                "message": str(exc),
                "active_generation_job_id": exc.active_generation_job_id,
            },
        ) from exc
    except NoSectionsReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    new_version = f"{int(latest.card_version.split('.')[0]) + 1}.0"
    audit_service.record(
        actor_id=principal.user_id,
        action=AuditAction.RAG_CARD_REGENERATE_TRIGGERED,
        target_type="rag_card",
        target_id=doc_id,
        setup_job_id=setup_job_id,
        payload={
            "generation_job_id": job.generation_job_id,
            "previous_card_version": latest.card_version,
            "new_card_version": new_version,
            "reason": payload.reason,
        },
    )
    return RegenerateRAGCardResponse(
        doc_id=doc_id,
        new_card_version=new_version,
        generation_job_id=job.generation_job_id,
        status=job.status,
        message="Regeneration job created. Run job to materialize new card_version.",
    )


# ============================================================
# T-S05-031: POST /rag-card-generation-jobs/{job_id}/cancel
# ============================================================


@router.post(
    "/{setup_job_id}/rag-card-generation-jobs/{generation_job_id}/cancel",
    response_model=CancelRAGCardJobResponse,
    summary="Cancel RAG card generation job (T-S05-031)",
)
def cancel_rag_card_generation_job(
    setup_job_id: str = Path(..., min_length=1),
    generation_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_GENERATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    job_repo: InMemoryRAGCardGenerationJobRepository = Depends(get_rag_card_job_repo),
    audit_service: AuditService = Depends(get_audit_service),
) -> CancelRAGCardJobResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_gen_job(
        job_repo=job_repo,
        generation_job_id=generation_job_id,
        setup_job_id=setup_job_id,
    )
    try:
        job.transition_to(RAGCardGenerationJobStatus.CANCELLED)
    except InvalidRAGCardJobTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "RAG_CARD_GENERATION_JOB_TERMINAL",
                "message": str(exc),
                "current_status": job.status.value,
            },
        ) from exc
    job.finished_at = datetime.now(tz=UTC)
    job.updated_at = job.finished_at
    job_repo.update(job)
    audit_service.record(
        actor_id=principal.user_id,
        action=AuditAction.RAG_CARD_GENERATION_CANCELLED,
        target_type="rag_card_generation_job",
        target_id=generation_job_id,
        setup_job_id=setup_job_id,
        payload={"cancelled_at": job.finished_at.isoformat()},
    )
    return CancelRAGCardJobResponse(
        generation_job_id=job.generation_job_id,
        status=job.status,
        message=f"Job {generation_job_id} cancelled",
    )
