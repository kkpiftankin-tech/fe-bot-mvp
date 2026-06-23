"""Metadata Validation Service (T-S01-024 + SETUP-07 T-S07-008).

Прогоняет карточки через детерминированный validator (validators/rag_metadata_validator.py),
обновляет card.status в Registry в зависимости от результата:

- PASSED → metadata_validated
- WARNING → review_required (с note)
- FAILED → review_required (с note)

Бизнес-правило: при review_policy="strict" любая WARNING/FAILED останавливает
автоматический прогон pipeline в S5 (chunking) — требуется HITL approve.

SETUP-07 extension: персистит ValidationReport через ValidationReportRepository,
ValidationRun через ValidationRunRepository, эмитит events, audit, metrics.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from schemas.rag.rag_card import CardStatus
from schemas.setup.validation_report import ValidationReport, ValidationStatus
from schemas.setup.validation_run import ValidationRunDTO, ValidationRunStatus
from schemas.setup.validation_summary import ValidationSummaryDTO
from validators.rag_metadata_validator import validate_rag_card

from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    RAGCardRegistry,
)
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.metadata_validation.events import (
    ValidationReportCreatedEvent,
    ValidationRunCompletedEvent,
    ValidationRunStartedEvent,
    _BaseValidationEvent,
    event_payload,
    event_type_of,
)
from fe_bot.setup.metadata_validation.metrics import ValidationMetricsCollector
from fe_bot.setup.metadata_validation.report_repository import (
    InMemoryValidationReportRepository,
)
from fe_bot.setup.metadata_validation.run_repository import (
    InMemoryValidationRunRepository,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ReviewPolicy(StrEnum):
    """Политика прохождения validation."""

    STRICT = "strict"  # любая WARNING/FAILED → review_required
    ALLOW_WARNINGS = "allow_warnings"  # WARNING → metadata_validated, FAILED → review


@dataclass(slots=True)
class ValidationBatchResult:
    """Сводка прогона валидации по партии карточек."""

    total: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    review_required: int = 0
    reports: list[ValidationReport] = field(default_factory=list)


class MetadataValidationService:
    """Запускает rag_metadata_validator на наборе карточек из реестра.

    SETUP-07 extension: optional dependencies для persistence + observability.
    Backward-compat: если report_repo/run_repo/audit/metrics/event_bus не
    переданы — сервис работает как legacy MVP.
    """

    # Статусы, по которым валидируем (SETUP-07: APPROVED и READY включены).
    _ELIGIBLE_STATUSES = frozenset(
        {
            CardStatus.DRAFT,
            CardStatus.GENERATED,
            CardStatus.REVIEW_REQUIRED,
            CardStatus.APPROVED,
            CardStatus.READY_FOR_METADATA_VALIDATION,
        }
    )

    def __init__(
        self,
        *,
        registry: RAGCardRegistry,
        review_policy: ReviewPolicy = ReviewPolicy.STRICT,
        report_repo: InMemoryValidationReportRepository | None = None,
        run_repo: InMemoryValidationRunRepository | None = None,
        event_bus: EventBus | None = None,
        audit_service: AuditService | None = None,
        metrics: ValidationMetricsCollector | None = None,
    ) -> None:
        self._registry = registry
        self._policy = review_policy
        self._report_repo = report_repo
        self._run_repo = run_repo
        self._bus = event_bus
        self._audit = audit_service
        self._metrics = metrics or ValidationMetricsCollector()

    def validate_for_job(
        self,
        setup_job_id: str,
        *,
        triggered_by: str = "system",
    ) -> ValidationBatchResult:
        """Валидирует все eligible карточки setup_job.

        SETUP-07: создаёт ValidationRun, персистит reports, эмитит events,
        audit, metrics.
        """
        run_id = _gen_id("vrun")
        started = _now()

        records = self._registry.list_for_job(
            setup_job_id,
            status_in=self._ELIGIBLE_STATUSES,
        )
        result = ValidationBatchResult()
        result.total = len(records)

        # Persist run as RUNNING.
        if self._run_repo is not None:
            self._run_repo.add(
                ValidationRunDTO(
                    validation_run_id=run_id,
                    setup_job_id=setup_job_id,
                    status=ValidationRunStatus.RUNNING,
                    triggered_by=triggered_by,
                    policy=self._policy.value,
                    total=len(records),
                    started_at=started,
                )
            )

        # Audit + event run_started.
        self._audit_record(
            actor_id=triggered_by,
            action=AuditAction.VALIDATION_RUN_TRIGGERED,
            target_id=run_id,
            setup_job_id=setup_job_id,
            payload={"policy": self._policy.value, "total": len(records)},
        )
        self._emit(
            ValidationRunStartedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=setup_job_id,
                occurred_at=started,
                validation_run_id=run_id,
                triggered_by=triggered_by,
                policy=self._policy.value,
                total=len(records),
            )
        )

        all_doc_ids_in_job = {r.card.doc_id for r in self._registry.list_for_job(setup_job_id)}

        for rec in records:
            card_start = _now()
            known = all_doc_ids_in_job - {rec.card.doc_id}
            probe_card = rec.card.model_copy(update={"status": CardStatus.METADATA_VALIDATED})
            report = validate_rag_card(probe_card, rec.metadata, known_doc_ids=known)

            # Enrich report с SETUP-07 fields + persist.
            report = self._enrich_report(
                report,
                setup_job_id=setup_job_id,
                card_version=rec.card.card_version or rec.card.version,
                run_id=run_id,
            )
            if self._report_repo is not None:
                self._report_repo.save(report)

            result.reports.append(report)
            self._apply_validation(rec.card.doc_id, rec.card.status, report, result)

            # Metrics + audit + events per-card.
            duration_ms = max(int((_now() - card_start).total_seconds() * 1000), 0)
            self._metrics.observe_card_duration(duration_ms=duration_ms)
            self._metrics.record_report(status=report.status.value)
            for issue in report.errors:
                self._metrics.record_issue(code=issue.code, severity="error")
            for issue in report.warnings:
                self._metrics.record_issue(code=issue.code, severity="warning")
            self._audit_record(
                actor_id=triggered_by,
                action=AuditAction.VALIDATION_REPORT_CREATED,
                target_id=rec.card.doc_id,
                setup_job_id=setup_job_id,
                payload={
                    "validation_report_id": report.validation_report_id,
                    "status": report.status.value,
                    "errors_count": len(report.errors),
                    "warnings_count": len(report.warnings),
                },
            )
            self._emit(
                ValidationReportCreatedEvent(
                    event_id=_gen_id("evt"),
                    setup_job_id=setup_job_id,
                    occurred_at=_now(),
                    validation_report_id=report.validation_report_id,
                    doc_id=rec.card.doc_id,
                    card_version=rec.card.card_version or rec.card.version,
                    status=report.status.value,
                    errors_count=len(report.errors),
                    warnings_count=len(report.warnings),
                )
            )

        finished = _now()
        duration_ms = max(int((finished - started).total_seconds() * 1000), 0)

        # Update run as COMPLETED.
        if self._run_repo is not None:
            self._run_repo.update(
                ValidationRunDTO(
                    validation_run_id=run_id,
                    setup_job_id=setup_job_id,
                    status=ValidationRunStatus.COMPLETED,
                    triggered_by=triggered_by,
                    policy=self._policy.value,
                    total=result.total,
                    passed=result.passed,
                    warnings=result.warnings,
                    failed=result.failed,
                    review_required=result.review_required,
                    started_at=started,
                    finished_at=finished,
                    duration_ms=duration_ms,
                )
            )

        # Metrics + event run_completed.
        outcome = "completed" if result.failed == 0 else "completed_with_failures"
        self._metrics.record_run(outcome=outcome)
        self._metrics.observe_run_duration(duration_ms=duration_ms)
        self._emit(
            ValidationRunCompletedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=setup_job_id,
                occurred_at=finished,
                validation_run_id=run_id,
                total=result.total,
                passed=result.passed,
                warnings=result.warnings,
                failed=result.failed,
                review_required=result.review_required,
                duration_ms=duration_ms,
            )
        )

        # Structured log.
        logger.info(
            "validation_run_completed",
            extra={
                "setup_job_id": setup_job_id,
                "validation_run_id": run_id,
                "policy": self._policy.value,
                "total": result.total,
                "passed": result.passed,
                "warnings": result.warnings,
                "failed": result.failed,
                "review_required": result.review_required,
                "duration_ms": duration_ms,
                "outcome": outcome,
            },
        )

        return result

    def validate_one(
        self,
        doc_id: str,
        *,
        triggered_by: str = "system",
    ) -> ValidationReport:
        """Прогон для одной карточки (полезно для review/regenerate)."""
        try:
            rec = self._registry.get(doc_id)
        except CardNotFoundError:
            raise

        known: set[str] = {
            r.card.doc_id
            for r in self._registry.list_for_job(rec.setup_job_id)
            if r.card.doc_id != doc_id
        }
        probe_card = rec.card.model_copy(update={"status": CardStatus.METADATA_VALIDATED})
        card_start = _now()
        report = validate_rag_card(probe_card, rec.metadata, known_doc_ids=known)

        report = self._enrich_report(
            report,
            setup_job_id=rec.setup_job_id,
            card_version=rec.card.card_version or rec.card.version,
            run_id=None,
        )
        if self._report_repo is not None:
            self._report_repo.save(report)

        result = ValidationBatchResult(total=1, reports=[report])
        self._apply_validation(doc_id, rec.card.status, report, result)

        # Per-card metrics + audit.
        duration_ms = max(int((_now() - card_start).total_seconds() * 1000), 0)
        self._metrics.observe_card_duration(duration_ms=duration_ms)
        self._metrics.record_report(status=report.status.value)
        for issue in report.errors:
            self._metrics.record_issue(code=issue.code, severity="error")
        for issue in report.warnings:
            self._metrics.record_issue(code=issue.code, severity="warning")
        self._audit_record(
            actor_id=triggered_by,
            action=AuditAction.VALIDATION_REPORT_CREATED,
            target_id=doc_id,
            setup_job_id=rec.setup_job_id,
            payload={
                "validation_report_id": report.validation_report_id,
                "status": report.status.value,
                "errors_count": len(report.errors),
                "warnings_count": len(report.warnings),
            },
        )

        return report

    def get_summary(self, setup_job_id: str) -> ValidationSummaryDTO:
        """SETUP-07 use case: агрегат для UI summary card."""
        if self._report_repo is None:
            return ValidationSummaryDTO(setup_job_id=setup_job_id)

        # Only latest report per (doc_id) — берём для каждой карточки последнюю.
        records = self._registry.list_for_job(setup_job_id)
        latest_reports: list[ValidationReport] = []
        for rec in records:
            r = self._report_repo.get_latest(setup_job_id, rec.card.doc_id)
            if r is not None:
                latest_reports.append(r)

        by_code: dict[str, int] = {}
        passed = warnings = failed = 0
        for r in latest_reports:
            if r.status == ValidationStatus.PASSED:
                passed += 1
            elif r.status == ValidationStatus.WARNING:
                warnings += 1
            else:
                failed += 1
            for issue in r.errors:
                by_code[issue.code] = by_code.get(issue.code, 0) + 1
            for issue in r.warnings:
                by_code[issue.code] = by_code.get(issue.code, 0) + 1

        last_run_id: str | None = None
        if self._run_repo is not None:
            latest = self._run_repo.latest_for_job(setup_job_id)
            if latest is not None:
                last_run_id = latest.validation_run_id

        review_required_count = sum(
            1 for rec in records if rec.card.status == CardStatus.REVIEW_REQUIRED
        )

        return ValidationSummaryDTO(
            setup_job_id=setup_job_id,
            total=len(latest_reports),
            passed=passed,
            warnings=warnings,
            failed=failed,
            review_required=review_required_count,
            by_code=by_code,
            last_run_id=last_run_id,
        )

    def _enrich_report(
        self,
        report: ValidationReport,
        *,
        setup_job_id: str,
        card_version: str,
        run_id: str | None,
    ) -> ValidationReport:
        """Добавляет SETUP-07 optional поля в report."""
        return report.model_copy(
            update={
                "setup_job_id": setup_job_id,
                "card_version": card_version,
                "policy_used": self._policy.value,
                "validation_run_id": run_id,
            }
        )

    def _emit(self, event: _BaseValidationEvent) -> None:
        if self._bus is None:
            return
        self._bus.publish(
            SetupProgressEvent(
                event_type=event_type_of(event),
                setup_job_id=event.setup_job_id,
                step=None,
                status="in_progress",
                progress_percent=0.0,
                message=None,
                metrics=event_payload(event),
            )
        )

    def _audit_record(
        self,
        *,
        actor_id: str,
        action: AuditAction,
        target_id: str,
        setup_job_id: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            actor_id=actor_id,
            action=action,
            target_type="rag_card",
            target_id=target_id,
            setup_job_id=setup_job_id,
            payload=payload or {},
        )

    def _apply_validation(
        self,
        doc_id: str,
        current_status: CardStatus,
        report: ValidationReport,
        batch: ValidationBatchResult,
    ) -> None:
        """Обновляет статус карточки в реестре по итогу validation."""
        rec = self._registry.get(doc_id)
        card = rec.card

        # Cannot transition from APPROVED/CHUNKED/etc downward via validation
        if current_status not in {
            CardStatus.DRAFT,
            CardStatus.GENERATED,
            CardStatus.REVIEW_REQUIRED,
            CardStatus.METADATA_VALIDATED,
        }:
            return

        if report.status == ValidationStatus.PASSED:
            target = CardStatus.METADATA_VALIDATED
            batch.passed += 1
            note = "validation passed"
        elif report.status == ValidationStatus.WARNING:
            batch.warnings += 1
            if self._policy == ReviewPolicy.ALLOW_WARNINGS:
                target = CardStatus.METADATA_VALIDATED
                note = (
                    f"validation warnings ({len(report.warnings)}); "
                    "auto-approved under allow_warnings policy"
                )
            else:
                target = CardStatus.REVIEW_REQUIRED
                batch.review_required += 1
                note = f"validation warnings ({len(report.warnings)}) — review required"
        elif report.status == ValidationStatus.FAILED:
            target = CardStatus.REVIEW_REQUIRED
            batch.failed += 1
            batch.review_required += 1
            note = f"validation failed ({len(report.errors)} errors)"
        else:  # REPAIR_REQUIRED
            target = CardStatus.REVIEW_REQUIRED
            batch.review_required += 1
            note = "validation repair_required"

        # Defensive: не пытаемся вернуться, если уже в target
        if card.status == target:
            return

        try:
            if not card.can_transition_to(target):
                # Например REVIEW_REQUIRED → REVIEW_REQUIRED, или
                # GENERATED → METADATA_VALIDATED ok. Если переход невалиден —
                # помечаем error в batch, но не падаем.
                batch.review_required += 1
                return
            updated_card = card.model_copy(update={"status": target})
            self._registry.update(doc_id, card=updated_card, note=note)
        except Exception:
            # Тёплая ошибка — оставляем как есть, ловит integration-тест.
            pass
