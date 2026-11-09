"""SETUP-07 metadata validation endpoints (T-S07-012).

5 endpoints под /api/v1/setup/{setup_job_id}/...:

- POST /validation/run              — запуск batch validation
- GET  /validation/reports          — список reports
- GET  /validation/reports/{doc_id} — latest report по карточке
- POST /validation/reports/{doc_id}/refresh — re-validate одной карточки
- GET  /validation/summary          — агрегат для UI
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from schemas.setup.validation_report import ValidationReport

from fe_bot.api.dependencies import (
    get_card_registry,
    get_metadata_validation,
    get_orchestrator,
    get_validation_report_repo,
    get_validation_run_repo,
    require_permission,
)
from fe_bot.api.setup.validation_dto import (
    RefreshValidationRequest,
    RunValidationRequest,
    ValidationCheckItemDTO,
    ValidationIssueItemDTO,
    ValidationReportItemDTO,
    ValidationReportListResponse,
    ValidationRunResponse,
    ValidationSummaryResponse,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.metadata_validation.report_repository import (
    InMemoryValidationReportRepository,
)
from fe_bot.setup.metadata_validation.run_repository import (
    InMemoryValidationRunRepository,
)
from fe_bot.setup.metadata_validation.service import MetadataValidationService
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.repository import JobNotFoundError

router = APIRouter(prefix="/api/v1/setup", tags=["validation"])


_CROSS_JOB_PERMISSIONS = (
    Permission.KB_PUBLISH,
    Permission.KB_CARD_REVIEW,
)


def _check_job_access(job, principal: Principal) -> None:
    if job.user_id == principal.user_id:
        return
    if any(principal.has_permission(p) for p in _CROSS_JOB_PERMISSIONS):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cannot access validation of another user's setup job",
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


def _report_to_dto(report: ValidationReport) -> ValidationReportItemDTO:
    return ValidationReportItemDTO(
        validation_report_id=report.validation_report_id,
        setup_job_id=report.setup_job_id,
        doc_id=report.target_id,
        card_version=report.card_version,
        status=report.status.value,
        errors=[
            ValidationIssueItemDTO(
                code=i.code,
                field=i.field,
                message=i.message,
                severity=i.severity.value,
                details=i.details,
            )
            for i in report.errors
        ],
        warnings=[
            ValidationIssueItemDTO(
                code=i.code,
                field=i.field,
                message=i.message,
                severity=i.severity.value,
                details=i.details,
            )
            for i in report.warnings
        ],
        checks=[
            ValidationCheckItemDTO(name=c.name, passed=c.passed)
            for c in report.checks
        ],
        policy_used=report.policy_used,
        validation_run_id=report.validation_run_id,
        validator_name=report.validator_name,
        created_at=report.created_at,
    )


# ============================================================
# POST /validation/run
# ============================================================


@router.post(
    "/{setup_job_id}/validation/run",
    response_model=ValidationRunResponse,
    summary="Run batch metadata validation (T-S07-012)",
)
def run_validation(
    payload: RunValidationRequest | None = None,
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_VALIDATION_RUN)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    svc: MetadataValidationService = Depends(get_metadata_validation),
    run_repo: InMemoryValidationRunRepository = Depends(get_validation_run_repo),
) -> ValidationRunResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    svc.validate_for_job(setup_job_id, triggered_by=principal.user_id)
    run = run_repo.latest_for_job(setup_job_id)
    if run is None:
        raise HTTPException(status_code=500, detail="Validation run not persisted")
    return ValidationRunResponse(
        validation_run_id=run.validation_run_id,
        setup_job_id=run.setup_job_id,
        status=run.status.value,
        triggered_by=run.triggered_by,
        policy=run.policy,
        total=run.total,
        passed=run.passed,
        warnings=run.warnings,
        failed=run.failed,
        review_required=run.review_required,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
    )


# ============================================================
# GET /validation/reports
# ============================================================


@router.get(
    "/{setup_job_id}/validation/reports",
    response_model=ValidationReportListResponse,
    summary="List validation reports (T-S07-012)",
)
def list_validation_reports(
    setup_job_id: str = Path(..., min_length=1),
    status_filter: str | None = Query(default=None, alias="status"),
    code_filter: str | None = Query(default=None, alias="code"),
    principal: Principal = Depends(require_permission(Permission.KB_VALIDATION_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    report_repo: InMemoryValidationReportRepository = Depends(
        get_validation_report_repo
    ),
) -> ValidationReportListResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    reports = report_repo.list_for_job(setup_job_id)
    if status_filter:
        reports = [r for r in reports if r.status.value == status_filter]
    if code_filter:
        reports = [
            r
            for r in reports
            if any(i.code == code_filter for i in r.errors + r.warnings)
        ]
    return ValidationReportListResponse(
        setup_job_id=setup_job_id,
        items=[_report_to_dto(r) for r in reports],
        total=len(reports),
    )


# ============================================================
# GET /validation/reports/{doc_id}
# ============================================================


@router.get(
    "/{setup_job_id}/validation/reports/{doc_id}",
    response_model=ValidationReportItemDTO,
    summary="Get latest validation report for card (T-S07-012)",
)
def get_validation_report(
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_VALIDATION_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    report_repo: InMemoryValidationReportRepository = Depends(
        get_validation_report_repo
    ),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> ValidationReportItemDTO:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    # Cross-job isolation: карточка должна принадлежать setup_job.
    try:
        rec = card_registry.get(doc_id)
    except CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if rec.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=404,
            detail=f"Card {doc_id!r} not found in setup_job {setup_job_id!r}",
        )

    report = report_repo.get_latest(setup_job_id, doc_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"No validation report found for {doc_id!r}",
        )
    return _report_to_dto(report)


# ============================================================
# POST /validation/reports/{doc_id}/refresh
# ============================================================


@router.post(
    "/{setup_job_id}/validation/reports/{doc_id}/refresh",
    response_model=ValidationReportItemDTO,
    summary="Re-validate single card (T-S07-012)",
)
def refresh_validation_report(
    payload: RefreshValidationRequest | None = None,
    setup_job_id: str = Path(..., min_length=1),
    doc_id: str = Path(..., min_length=1),
    principal: Principal = Depends(
        require_permission(Permission.KB_VALIDATION_REFRESH)
    ),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    svc: MetadataValidationService = Depends(get_metadata_validation),
    card_registry: InMemoryRAGCardRegistry = Depends(get_card_registry),
) -> ValidationReportItemDTO:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    try:
        rec = card_registry.get(doc_id)
    except CardNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if rec.setup_job_id != setup_job_id:
        raise HTTPException(
            status_code=404,
            detail=f"Card {doc_id!r} not found in setup_job {setup_job_id!r}",
        )
    report = svc.validate_one(doc_id, triggered_by=principal.user_id)
    return _report_to_dto(report)


# ============================================================
# GET /validation/summary
# ============================================================


@router.get(
    "/{setup_job_id}/validation/summary",
    response_model=ValidationSummaryResponse,
    summary="Get validation summary aggregate (T-S07-012)",
)
def get_validation_summary(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_VALIDATION_READ)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    svc: MetadataValidationService = Depends(get_metadata_validation),
) -> ValidationSummaryResponse:
    _load_setup_job(
        orchestrator=orchestrator,
        setup_job_id=setup_job_id,
        principal=principal,
    )
    summary = svc.get_summary(setup_job_id)
    return ValidationSummaryResponse(
        setup_job_id=summary.setup_job_id,
        total=summary.total,
        passed=summary.passed,
        warnings=summary.warnings,
        failed=summary.failed,
        review_required=summary.review_required,
        by_code=summary.by_code,
        last_run_id=summary.last_run_id,
    )
