"""SETUP-04 Parse endpoints (T-S04-023..026).

6 endpoints под /api/v1/setup/{setup_job_id}/parse-jobs:
- POST   /parse-jobs                                 — создать ParseJob
- GET    /parse-jobs/{parse_job_id}                  — статус
- GET    /parse-jobs/{parse_job_id}/report           — отчёт по документам
- GET    /parse-jobs/{parse_job_id}/sections         — список секций
- POST   /parse-jobs/{parse_job_id}/cancel           — cancel job
- POST   /parse-jobs/{parse_job_id}/documents/{src_id}/retry — retry упавшего документа
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from schemas.setup.parse_job import (
    InvalidParseJobTransitionError,
    ParseErrorCode,
    ParseJob,
    ParseJobStatus,
)
from schemas.setup.parse_job_document import ParseJobDocumentStatus
from schemas.setup.parsed_section import (
    ParsedSection,
    ParsedSectionStatus,
    SectionType,
)
from schemas.setup.rag_setup_job import RAGSetupJob

from fe_bot.api.dependencies import (
    get_document_parser_orchestrator,
    get_orchestrator,
    get_parse_document_repo,
    get_parse_job_repo,
    get_parse_report_repo,
    get_parsed_section_repo,
    require_permission,
)
from fe_bot.api.setup.parse_dto import (
    CancelParseJobResponse,
    CreateParseJobRequest,
    DocumentReportDTO,
    PaginationDTO,
    ParsedSectionListItemDTO,
    ParsedSectionsResponse,
    ParseJobReportResponse,
    ParseJobResponse,
    RetryParseDocumentResponse,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.parser.document_repository import (
    InMemoryParseJobDocumentRepository,
    ParseJobDocumentNotFoundError,
)
from fe_bot.setup.parser.job_repository import (
    InMemoryParseJobRepository,
    ParseJobNotFoundError,
)
from fe_bot.setup.parser.orchestrator import (
    DocumentParserOrchestrator,
    NoParseableDocumentsError,
    ParseJobAlreadyRunningError,
)
from fe_bot.setup.parser.report_repository import (
    InMemoryDocumentParseReportRepository,
)
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.repository import JobNotFoundError

router = APIRouter(prefix="/api/v1/setup", tags=["parse"])

_CROSS_JOB_PERMISSIONS = (Permission.KB_PUBLISH, Permission.KB_CARD_REVIEW)


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
        detail="Cannot access parse jobs of another user's setup job",
    )


def _load_job(
    *,
    orchestrator: SetupOrchestrator,
    setup_job_id: str,
    principal: Principal,
) -> RAGSetupJob:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _check_job_access(job, principal)
    return job


def _load_parse_job(*, parse_job_repo: InMemoryParseJobRepository, parse_job_id: str) -> ParseJob:
    try:
        return parse_job_repo.get(parse_job_id)
    except ParseJobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _ensure_parse_job_in_setup(parse_job: ParseJob, setup_job_id: str) -> None:
    if parse_job.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"ParseJob {parse_job.parse_job_id!r} does not belong to setup_job {setup_job_id!r}"
            ),
        )


def _to_parse_job_response(job: ParseJob) -> ParseJobResponse:
    return ParseJobResponse(
        parse_job_id=job.parse_job_id,
        setup_job_id=job.setup_job_id,
        status=job.status,
        total_documents=job.total_documents,
        processed_documents=job.processed_documents,
        failed_documents=job.failed_documents,
        total_sections=job.total_sections,
        low_confidence_sections=job.low_confidence_sections,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_code=job.error_code,
        error_message=job.error_message,
    )


def _to_section_list_item(section: ParsedSection) -> ParsedSectionListItemDTO:
    return ParsedSectionListItemDTO(
        section_id=section.section_id,
        source_document_id=section.source_document_id,
        title=section.title,
        section_type=section.section_type,
        section_status=section.section_status,
        confidence=section.confidence,
        heading_path=list(section.heading_path),
        section_index=section.section_index,
        parent_section_id=section.parent_section_id,
        content_hash=section.content_hash,
    )


def _paginate[T](items: list[T], page: int, page_size: int) -> tuple[list[T], PaginationDTO]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], PaginationDTO(page=page, page_size=page_size, total=total)


# ============================================================
# T-S04-023: POST /parse-jobs
# ============================================================


@router.post(
    "/{setup_job_id}/parse-jobs",
    response_model=ParseJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ParseJob (T-S04-023)",
)
def create_parse_job(
    payload: CreateParseJobRequest,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parser_orchestrator: DocumentParserOrchestrator = Depends(get_document_parser_orchestrator),
) -> ParseJobResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    try:
        job = parser_orchestrator.create_parse_job(
            setup_job_id=setup_job_id,
            requested_by=principal.user_id,
            config=payload.config,
        )
    except ParseJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ParseErrorCode.PARSE_JOB_ALREADY_RUNNING.value,
                "message": str(exc),
                "active_parse_job_id": exc.active_parse_job_id,
            },
        ) from exc
    except NoParseableDocumentsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ParseErrorCode.NO_PARSEABLE_DOCUMENTS.value,
                "message": str(exc),
            },
        ) from exc
    return _to_parse_job_response(job)


# ============================================================
# T-S04-024: GET status + report
# ============================================================


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}",
    response_model=ParseJobResponse,
    summary="Get ParseJob status (T-S04-024)",
)
def get_parse_job_status(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_STATUS_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
) -> ParseJobResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)
    return _to_parse_job_response(job)


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/report",
    response_model=ParseJobReportResponse,
    summary="Get ParseJob report (T-S04-024)",
)
def get_parse_job_report(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_STATUS_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    report_repo: InMemoryDocumentParseReportRepository = Depends(get_parse_report_repo),
) -> ParseJobReportResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)
    reports = report_repo.list_for_job(parse_job_id)
    documents = [
        DocumentReportDTO(
            source_document_id=r.source_document_id,
            status=r.status,
            parser_strategy=r.parser_strategy,
            sections_count=r.summary.sections_count,
            sections_by_type=dict(r.summary.sections_by_type),
            low_confidence_sections=r.summary.low_confidence_sections,
            errors=list(r.errors),
            warnings=list(r.warnings),
            created_at=r.created_at,
        )
        for r in reports
    ]
    return ParseJobReportResponse(
        parse_job_id=parse_job_id,
        setup_job_id=setup_job_id,
        status=job.status,
        documents=documents,
    )


# ============================================================
# T-S04-025: GET sections + POST cancel
# ============================================================


@router.get(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/sections",
    response_model=ParsedSectionsResponse,
    summary="List parsed sections (T-S04-025)",
)
def list_parsed_sections(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    source_document_id: str | None = Query(default=None, min_length=1),
    section_type: SectionType | None = Query(default=None),
    section_status: ParsedSectionStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: Principal = Depends(require_permission(Permission.KB_SECTION_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    section_repo: InMemoryParsedSectionRepository = Depends(get_parsed_section_repo),
) -> ParsedSectionsResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)

    sections = section_repo.list_for_job(parse_job_id)
    if source_document_id is not None:
        sections = [s for s in sections if s.source_document_id == source_document_id]
    if section_type is not None:
        sections = [s for s in sections if s.section_type == section_type]
    if section_status is not None:
        sections = [s for s in sections if s.section_status == section_status]

    paged, pagination = _paginate(sections, page, page_size)
    return ParsedSectionsResponse(
        parse_job_id=parse_job_id,
        items=[_to_section_list_item(s) for s in paged],
        pagination=pagination,
    )


@router.post(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/cancel",
    response_model=CancelParseJobResponse,
    summary="Cancel ParseJob (T-S04-025)",
)
def cancel_parse_job(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_CANCEL)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
) -> CancelParseJobResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)

    try:
        job.transition_to(ParseJobStatus.CANCELLED)
    except InvalidParseJobTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "PARSE_JOB_TERMINAL",
                "message": str(exc),
                "current_status": job.status.value,
            },
        ) from exc
    parse_job_repo.update(job)
    return CancelParseJobResponse(
        parse_job_id=job.parse_job_id,
        status=job.status,
        message=f"ParseJob {parse_job_id} cancelled",
    )


# ============================================================
# T-S04-026: POST retry document
# ============================================================


@router.post(
    "/{setup_job_id}/parse-jobs/{parse_job_id}/documents/{source_document_id}/retry",
    response_model=RetryParseDocumentResponse,
    summary="Retry failed document (T-S04-026)",
)
def retry_parse_document(
    setup_job_id: str = Path(..., min_length=1),
    parse_job_id: str = Path(..., min_length=1),
    source_document_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_PARSE_RETRY)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    parser_orchestrator: DocumentParserOrchestrator = Depends(get_document_parser_orchestrator),
    parse_job_repo: InMemoryParseJobRepository = Depends(get_parse_job_repo),
    document_repo: InMemoryParseJobDocumentRepository = Depends(get_parse_document_repo),
) -> RetryParseDocumentResponse:
    _load_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    job = _load_parse_job(parse_job_repo=parse_job_repo, parse_job_id=parse_job_id)
    _ensure_parse_job_in_setup(job, setup_job_id)

    matched = [
        d
        for d in document_repo.list_for_job(parse_job_id)
        if d.source_document_id == source_document_id
    ]
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"Document {source_document_id!r} not in parse_job {parse_job_id!r}"),
        )
    target_doc = matched[-1]
    if target_doc.status != ParseJobDocumentStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ParseErrorCode.DOCUMENT_NOT_PARSEABLE_STATUS.value,
                "message": (f"Document status is {target_doc.status.value}; retry only for FAILED"),
            },
        )

    # MVP-стратегия: создаём новый ParseJob для одного документа,
    # это упрощает rollback и аудит — не мутируем counters старого job'а.
    try:
        new_job = parser_orchestrator.create_parse_job(
            setup_job_id=setup_job_id,
            requested_by=principal.user_id,
            config={"retry_of": parse_job_id, "source_document_id": source_document_id},
        )
    except ParseJobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": ParseErrorCode.PARSE_JOB_ALREADY_RUNNING.value,
                "message": str(exc),
                "active_parse_job_id": exc.active_parse_job_id,
            },
        ) from exc
    except NoParseableDocumentsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ParseErrorCode.NO_PARSEABLE_DOCUMENTS.value,
                "message": str(exc),
            },
        ) from exc
    return RetryParseDocumentResponse(
        parse_job_id=parse_job_id,
        source_document_id=source_document_id,
        status=ParseJobDocumentStatus.PENDING,
        message=f"Retry queued via new ParseJob {new_job.parse_job_id}",
        new_parse_job_id=new_job.parse_job_id,
    )


# Re-export of error classes for tests that want to introspect.
__all__ = [
    "ParseJobDocumentNotFoundError",
    "router",
]
