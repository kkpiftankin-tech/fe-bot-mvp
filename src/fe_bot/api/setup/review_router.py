"""SETUP-06 RAG card review endpoints (T-S06-026).

9 endpoints под /api/v1/setup/{setup_job_id}/...:

- GET   /rag-cards-review                                  — список карточек
- GET   /rag-cards-review/{doc_id}                         — details
- GET   /rag-cards-review/{doc_id}/versions                — версии
- GET   /rag-cards-review/{doc_id}/diff                    — diff
- GET   /rag-cards-review/{doc_id}/review-log              — журнал
- POST  /rag-cards-review/{doc_id}/review                  — approve/reject
- PATCH /rag-cards-review/{doc_id}                         — edit
- POST  /rag-cards-review/{doc_id}/regenerate              — regenerate
- POST  /rag-cards-review/bulk-review                      — bulk approve
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from fe_bot.api.dependencies import (
    get_card_registry,
    get_card_review,
    get_orchestrator,
    require_permission,
)
from fe_bot.api.setup.review_dto import (
    ApproveResponse,
    BulkReviewItemResult,
    BulkReviewRequest,
    BulkReviewResponse,
    CardDiffResponse,
    CardVersionItemDTO,
    EditRAGCardRequest,
    EditResponse,
    RAGCardReviewDetailsDTO,
    RAGCardReviewListItemDTO,
    RAGCardReviewListResponse,
    RAGCardVersionsResponse,
    RegenerateRAGCardReviewRequest,
    RegenerateReviewResponse,
    RejectResponse,
    ReviewLogItemDTO,
    ReviewLogResponse,
    ReviewPermissionsDTO,
    ReviewRAGCardRequest,
    ReviewSummary,
    ValidationItemDTO,
    ValidationReportDTO,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.card_review.service import (
    CardHasCriticalValidationErrorsError,
    CardVersionConflictError,
    InvalidEditPayloadError,
    InvalidReviewStateError,
    Pagination,
    RAGCardReviewService,
    ReviewListFilters,
)
from fe_bot.setup.card_review.editor import SystemMetadataReadOnlyError
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.repository import JobNotFoundError

router = APIRouter(prefix="/api/v1/setup", tags=["rag-cards-review"])


_CROSS_JOB_PERMISSIONS = (
    Permission.KB_PUBLISH,
    Permission.KB_CARD_REVIEW,
)


# ============================================================
# Helpers
# ============================================================


def _check_job_access(job, principal: Principal) -> None:
    if job.user_id == principal.user_id:
        return
    if any(principal.has_permission(p) for p in _CROSS_JOB_PERMISSIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot access review of another user's setup job",
    )


def _load_setup_job(
    *,
    orchestrator: SetupOrchestrator,
    setup_job_id: str,
    principal: Principal,
):
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _check_job_access(job, principal)
    return job


def _load_card(
    *,
    card_registry: InMemoryRAGCardRegistry,
    doc_id: str,
    setup_job_id: str,
):
    try:
        record = card_registry.get(doc_id)
    except CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if record.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=404,
            detail=f"Card {doc_id!r} not found in setup_job {setup_job_id!r}",
        )
    return record


# ============================================================
# GET /rag-cards-review — list
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards-review",
    response_model=RAGCardReviewListResponse,
    summary="List RAG cards for review (T-S06-026)",
)
def list_review_cards(
    setup_job_id: str = Path(..., min_length=1),
    doc_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    confidence_level: str | None = Query(default=None),
    source_document_id: str | None = Query(default=None),
    has_validation_errors: bool | None = Query(default=None),
    review_required: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_LIST)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
) -> RAGCardReviewListResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    filters = ReviewListFilters(
        doc_type=doc_type,
        status=status_filter,
        confidence_level=confidence_level,
        source_document_id=source_document_id,
        has_validation_errors=has_validation_errors,
        review_required=review_required,
    )
    pagination = Pagination(page=page, page_size=page_size)
    resp = review_service.list_review_cards(
        setup_job_id, filters=filters, pagination=pagination
    )
    return RAGCardReviewListResponse(
        setup_job_id=resp.setup_job_id,
        items=[
            RAGCardReviewListItemDTO(
                doc_id=i.doc_id,
                card_version=i.card_version,
                title=i.title,
                doc_type=i.doc_type,
                status=i.status,
                confidence_level=i.confidence_level,
                source_document_id=i.source_document_id,
                source_section_id=i.source_section_id,
                validation_errors_count=i.validation_errors_count,
                warnings_count=i.warnings_count,
                review_required_reason=i.review_required_reason,
                last_reviewed_by=i.last_reviewed_by,
                updated_at=i.updated_at,
            )
            for i in resp.items
        ],
        total=resp.total,
        page=resp.page,
        page_size=resp.page_size,
        summary=ReviewSummary(
            total=resp.summary.get("total", 0),
            by_status={k: v for k, v in resp.summary.items() if k != "total"},
        ),
    )


# ============================================================
# GET /rag-cards-review/{doc_id} — details
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards-review/{doc_id}",
    response_model=RAGCardReviewDetailsDTO,
    summary="Get RAG card details for review (T-S06-026)",
)
def get_review_card(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> RAGCardReviewDetailsDTO:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    _load_card(
        card_registry=card_registry, doc_id=doc_id, setup_job_id=setup_job_id
    )
    details = review_service.get_card_for_review(doc_id)
    return RAGCardReviewDetailsDTO(
        doc_id=details.doc_id,
        card_version=details.card_version,
        title=details.title,
        doc_type=details.doc_type,
        status=details.status,
        confidence_level=details.confidence_level,
        metadata=details.metadata,
        body_markdown=details.body_markdown,
        source_trace=details.source_trace,
        validation=ValidationReportDTO(
            critical_errors=[
                ValidationItemDTO(**e) for e in details.validation["critical_errors"]
            ],
            warnings=[
                ValidationItemDTO(**w) for w in details.validation["warnings"]
            ],
        ),
        review_log_count=details.review_log_count,
        permissions=ReviewPermissionsDTO(**details.permissions),
    )


# ============================================================
# GET /rag-cards-review/{doc_id}/versions
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards-review/{doc_id}/versions",
    response_model=RAGCardVersionsResponse,
    summary="Get RAG card version history (T-S06-026)",
)
def get_review_versions(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(
        require_permission(Permission.KB_RAG_CARD_VERSION_READ)
    ),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> RAGCardVersionsResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    _load_card(
        card_registry=card_registry, doc_id=doc_id, setup_job_id=setup_job_id
    )
    versions = review_service.get_card_versions(doc_id)
    return RAGCardVersionsResponse(
        doc_id=doc_id,
        versions=[
            CardVersionItemDTO(
                doc_id=v.doc_id,
                card_version=v.card_version,
                parent_card_version=v.parent_card_version,
                status=v.status.value,
                markdown_artifact_id=v.markdown_artifact_id,
                body_hash=v.body_hash,
                created_by=v.created_by,
                created_at=v.created_at,
                change_reason=v.change_reason,
                is_current=v.is_current,
            )
            for v in versions
        ],
    )


# ============================================================
# GET /rag-cards-review/{doc_id}/diff
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards-review/{doc_id}/diff",
    response_model=CardDiffResponse,
    summary="Get RAG card version diff (T-S06-026)",
)
def get_review_diff(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    from_version: str = Query(..., pattern=r"^\d+(\.\d+){0,2}$"),
    to_version: str = Query(..., pattern=r"^\d+(\.\d+){0,2}$"),
    principal: Principal = Depends(
        require_permission(Permission.KB_RAG_CARD_DIFF_READ)
    ),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> CardDiffResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    _load_card(
        card_registry=card_registry, doc_id=doc_id, setup_job_id=setup_job_id
    )
    try:
        diff = review_service.get_card_diff(
            doc_id, from_version=from_version, to_version=to_version
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CardDiffResponse(**diff)


# ============================================================
# GET /rag-cards-review/{doc_id}/review-log
# ============================================================


@router.get(
    "/{setup_job_id}/rag-cards-review/{doc_id}/review-log",
    response_model=ReviewLogResponse,
    summary="Get review log for RAG card (T-S06-026)",
)
def get_review_log(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    principal: Principal = Depends(
        require_permission(Permission.KB_RAG_CARD_REVIEW_LOG_READ)
    ),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> ReviewLogResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    _load_card(
        card_registry=card_registry, doc_id=doc_id, setup_job_id=setup_job_id
    )
    entries = review_service.get_review_log(doc_id, limit=limit)
    return ReviewLogResponse(
        doc_id=doc_id,
        items=[
            ReviewLogItemDTO(
                review_log_id=e.review_log_id,
                setup_job_id=e.setup_job_id,
                doc_id=e.doc_id,
                card_version=e.card_version,
                event_type=e.event_type.value,
                actor_id=e.actor_id,
                actor_role=e.actor_role,
                message=e.message,
                before_status=e.before_status,
                after_status=e.after_status,
                created_at=e.created_at,
                payload=e.payload,
            )
            for e in entries
        ],
    )


# ============================================================
# POST /rag-cards-review/{doc_id}/review — approve/reject
# ============================================================


@router.post(
    "/{setup_job_id}/rag-cards-review/{doc_id}/review",
    response_model=ApproveResponse | RejectResponse,
    summary="Approve or reject RAG card (T-S06-026)",
)
def review_card_decision(
    payload: ReviewRAGCardRequest,
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_APPROVE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
):
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    record = _load_card(
        card_registry=card_registry, doc_id=doc_id, setup_job_id=setup_job_id
    )

    decision_id = payload.review_decision_id or f"rd_{datetime.now(tz=UTC).timestamp()}"

    if payload.decision == "approve":
        try:
            updated = review_service.approve_card(
                doc_id=doc_id,
                reviewer_id=principal.user_id,
                reviewer_role=",".join(r.value for r in principal.roles),
                review_decision_id=decision_id,
                comment=payload.comment,
                setup_job_id=setup_job_id,
            )
        except CardHasCriticalValidationErrorsError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "CARD_HAS_CRITICAL_VALIDATION_ERRORS",
                    "doc_id": doc_id,
                    "codes": exc.codes,
                },
            ) from exc
        except InvalidReviewStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApproveResponse(
            doc_id=updated.card.doc_id,
            card_version=updated.card.card_version or updated.card.version,
            status=updated.card.status.value,
            review_decision_id=decision_id,
            reviewed_by=principal.user_id,
            reviewed_at=updated.card.updated_at,
        )
    else:  # reject
        # AC-23: reject требует reason
        if not payload.reason:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "REJECT_REASON_REQUIRED",
                    "message": "reject decision requires reason",
                },
            )
        try:
            updated = review_service.reject_card(
                doc_id=doc_id,
                reviewer_id=principal.user_id,
                reviewer_role=",".join(r.value for r in principal.roles),
                reason=payload.reason,
                comment=payload.comment,
                review_decision_id=decision_id,
                setup_job_id=setup_job_id,
            )
        except InvalidReviewStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RejectResponse(
            doc_id=updated.card.doc_id,
            card_version=updated.card.card_version or updated.card.version,
            status=updated.card.status.value,
            review_decision_id=decision_id,
            reason=payload.reason,
            reviewed_by=principal.user_id,
            reviewed_at=updated.card.updated_at,
        )


# ============================================================
# PATCH /rag-cards-review/{doc_id} — edit
# ============================================================


@router.patch(
    "/{setup_job_id}/rag-cards-review/{doc_id}",
    response_model=EditResponse,
    summary="Edit RAG card metadata/body (T-S06-026)",
)
def edit_review_card(
    payload: EditRAGCardRequest,
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_RAG_CARD_EDIT)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> EditResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    record = _load_card(
        card_registry=card_registry, doc_id=doc_id, setup_job_id=setup_job_id
    )
    previous_version = record.card.card_version or record.card.version

    try:
        updated = review_service.edit_card(
            doc_id=doc_id,
            reviewer_id=principal.user_id,
            reviewer_role=",".join(r.value for r in principal.roles),
            expected_version=payload.expected_version,
            metadata_patch=payload.metadata_patch,
            body_markdown=payload.body_markdown,
            change_reason=payload.change_reason,
            setup_job_id=setup_job_id,
        )
    except CardVersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "CARD_VERSION_CONFLICT",
                "expected": exc.expected,
                "current": exc.current,
            },
        ) from exc
    except SystemMetadataReadOnlyError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "SYSTEM_METADATA_READ_ONLY",
                "fields": exc.fields,
            },
        ) from exc
    except InvalidEditPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InvalidReviewStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return EditResponse(
        doc_id=updated.card.doc_id,
        previous_version=previous_version,
        new_version=updated.card.card_version or updated.card.version,
        status=updated.card.status.value,
        diff_available=True,
        edited_by=principal.user_id,
        edited_at=updated.card.updated_at,
    )


# ============================================================
# POST /rag-cards-review/{doc_id}/regenerate
# ============================================================


@router.post(
    "/{setup_job_id}/rag-cards-review/{doc_id}/regenerate",
    response_model=RegenerateReviewResponse,
    summary="Request RAG card regeneration via review flow (T-S06-026)",
)
def regenerate_review_card(
    payload: RegenerateRAGCardReviewRequest,
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(
        require_permission(Permission.KB_RAG_CARD_REGENERATE)
    ),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> RegenerateReviewResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    _load_card(
        card_registry=card_registry, doc_id=doc_id, setup_job_id=setup_job_id
    )

    try:
        updated = review_service.request_regeneration(
            doc_id=doc_id,
            reviewer_id=principal.user_id,
            reviewer_role=",".join(r.value for r in principal.roles),
            reason=payload.reason,
            instruction=payload.instruction,
            regenerate_request_id=payload.regenerate_request_id,
            setup_job_id=setup_job_id,
        )
    except InvalidReviewStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidEditPayloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Generation job id из decision metadata.
    return RegenerateReviewResponse(
        doc_id=updated.card.doc_id,
        card_version=updated.card.card_version or updated.card.version,
        status=updated.card.status.value,
        regenerate_request_id=payload.regenerate_request_id or "(auto)",
        generation_job_id=None,
        message="Regeneration requested",
    )


# ============================================================
# POST /rag-cards-review/bulk-review
# ============================================================


@router.post(
    "/{setup_job_id}/rag-cards-review/bulk-review",
    response_model=BulkReviewResponse,
    summary="Bulk approve RAG cards (T-S06-026)",
)
def bulk_review(
    payload: BulkReviewRequest,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(
        require_permission(Permission.KB_RAG_CARD_BULK_REVIEW)
    ),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    review_service: RAGCardReviewService = Depends(get_card_review),
) -> BulkReviewResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    items = [(it.doc_id, it.card_version) for it in payload.items]
    result = review_service.bulk_approve_cards(
        setup_job_id=setup_job_id,
        reviewer_id=principal.user_id,
        reviewer_role=",".join(r.value for r in principal.roles),
        items=items,
        comment=payload.comment,
        bulk_review_id=payload.bulk_review_id,
    )
    return BulkReviewResponse(
        bulk_review_id=result["bulk_review_id"],
        total=result["total"],
        approved=result["approved"],
        errors=result["errors"],
        results=[BulkReviewItemResult(**r) for r in result["results"]],
    )
