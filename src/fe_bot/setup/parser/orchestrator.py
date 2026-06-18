"""DocumentParserOrchestrator (SETUP-04 / T-S04-020/021/022).

Координатор парсинга документов:
1. Создаёт ParseJob поверх множества SourceDocument'ов одного RAGSetupJob.
2. Последовательно гоняет каждый документ через нужный ParserStrategy.
3. Применяет SectionClassifier и сохраняет ParsedSection пакетами.
4. Создаёт DocumentParseReport и обновляет lifecycle (статусы + lineage +
   processing log) через SourceLifecycleService.
5. Эмитит ParseJob-events, audit-записи и метрики.

Все операции in-process и синхронные — это MVP. Параллельная обработка и
очереди будут добавлены позже.
"""

from __future__ import annotations

import contextlib
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.parse_job import (
    ParseErrorCode,
    ParseJob,
    ParseJobStatus,
)
from schemas.setup.parse_job import (
    ParserStrategy as ParserStrategyEnum,
)
from schemas.setup.parse_job_document import (
    ParseJobDocument,
    ParseJobDocumentStatus,
)
from schemas.setup.parse_report import (
    DocumentParseReport,
    SectionsSummary,
)
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus

from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.parser.classifier import SectionClassifier
from fe_bot.setup.parser.document_repository import (
    InMemoryParseJobDocumentRepository,
)
from fe_bot.setup.parser.events import (
    ParseDocumentCompletedEvent,
    ParseDocumentFailedEvent,
    ParseDocumentStartedEvent,
    ParsedSectionsCreatedEvent,
    ParseJobCompletedEvent,
    ParseJobCreatedEvent,
    ParseJobFailedEvent,
    ParseJobPartialSuccessEvent,
    ParseJobStartedEvent,
    SectionClassificationLowConfidenceEvent,
    _BaseParseEvent,
    event_payload,
    event_type_of,
)
from fe_bot.setup.parser.job_repository import (
    DuplicateParseJobError,
    InMemoryParseJobRepository,
)
from fe_bot.setup.parser.registry import (
    ParseFailedError,
    ParserRegistry,
    UnsupportedFormatError,
)
from fe_bot.setup.parser.report_repository import (
    InMemoryDocumentParseReportRepository,
)
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.source_registry.lifecycle import SourceLifecycleService
from fe_bot.storage.artifact_service import ArtifactStorage

_DEFAULT_CONFIDENCE_THRESHOLD = 0.7

_PARSEABLE_STATUSES = frozenset(
    {
        SourceDocumentStatus.WAITING_FOR_PARSING,
        SourceDocumentStatus.REGISTERED,
    }
)


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _confidence_bucket(value: float) -> str:
    if value >= 0.9:
        return "high"
    if value >= 0.7:
        return "medium"
    return "low"


class ParseJobAlreadyRunningError(Exception):
    """Активный ParseJob уже существует для setup_job_id."""

    def __init__(self, setup_job_id: str, active_parse_job_id: str) -> None:
        self.setup_job_id = setup_job_id
        self.active_parse_job_id = active_parse_job_id
        super().__init__(
            f"Active ParseJob {active_parse_job_id} already exists for setup_job {setup_job_id}"
        )


class NoParseableDocumentsError(Exception):
    """В setup_job нет документов, готовых к парсингу."""

    def __init__(self, setup_job_id: str) -> None:
        self.setup_job_id = setup_job_id
        super().__init__(f"No parseable documents for setup_job {setup_job_id}")


class DocumentParserOrchestrator:
    """Фасад над парсером для одного RAGSetupJob.

    Не владеет ни ParserStrategy, ни ArtifactStorage напрямую — получает их
    через DI, что делает компонент тестируемым и совместимым с разными
    storage-бэкендами.
    """

    def __init__(
        self,
        *,
        parse_job_repo: InMemoryParseJobRepository,
        document_repo: InMemoryParseJobDocumentRepository,
        section_repo: InMemoryParsedSectionRepository,
        report_repo: InMemoryDocumentParseReportRepository,
        parser_registry: ParserRegistry,
        classifier: SectionClassifier,
        source_lifecycle: SourceLifecycleService,
        artifact_storage: ArtifactStorage,
        event_bus: EventBus | None = None,
        audit_service: AuditService | None = None,
        metrics: MetricsRegistry | None = None,
        confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._jobs = parse_job_repo
        self._docs = document_repo
        self._sections = section_repo
        self._reports = report_repo
        self._registry = parser_registry
        self._classifier = classifier
        self._lifecycle = source_lifecycle
        self._storage = artifact_storage
        self._bus = event_bus
        self._audit = audit_service
        self._metrics = metrics
        self._threshold = confidence_threshold

    # ============================================================
    # Public API
    # ============================================================

    def create_parse_job(
        self,
        *,
        setup_job_id: str,
        requested_by: str,
        config: dict[str, Any] | None = None,
    ) -> ParseJob:
        """Создаёт ParseJob поверх eligible документов setup_job'а."""
        active = self._jobs.get_active_for_setup_job(setup_job_id)
        if active is not None:
            raise ParseJobAlreadyRunningError(setup_job_id, active.parse_job_id)

        documents = self._eligible_documents(setup_job_id)
        if not documents:
            raise NoParseableDocumentsError(setup_job_id)

        now = _now()
        parse_job_id = _gen_id("pj")
        job = ParseJob(
            parse_job_id=parse_job_id,
            setup_job_id=setup_job_id,
            requested_by=requested_by,
            status=ParseJobStatus.CREATED,
            total_documents=len(documents),
            created_at=now,
            updated_at=now,
            config=config or {},
        )
        try:
            self._jobs.create(job)
        except DuplicateParseJobError as exc:
            raise ParseJobAlreadyRunningError(setup_job_id, exc.parse_job_id) from exc

        for doc in documents:
            self._docs.add(
                ParseJobDocument(
                    parse_job_document_id=_gen_id("pjd"),
                    parse_job_id=parse_job_id,
                    source_document_id=doc.source_document_id,
                    status=ParseJobDocumentStatus.PENDING,
                )
            )
            self._lifecycle.update_status(
                source_document_id=doc.source_document_id,
                new_status=SourceDocumentStatus.WAITING_FOR_PARSING,
                event_id=f"{parse_job_id}:waiting:{doc.source_document_id}",
                reason=f"Queued for ParseJob {parse_job_id}",
            )

        self._emit(
            ParseJobCreatedEvent(
                event_id=_gen_id("evt"),
                parse_job_id=parse_job_id,
                setup_job_id=setup_job_id,
                occurred_at=now,
                total_documents=len(documents),
                requested_by=requested_by,
            )
        )
        self._audit_record(
            actor_id=requested_by,
            action=AuditAction.PROCESSING_RETRY_TRIGGERED,
            target_type="parse_job",
            target_id=parse_job_id,
            setup_job_id=setup_job_id,
            payload={"event": "parse_job_created", "total_documents": len(documents)},
        )
        return job

    def run(self, parse_job_id: str) -> ParseJob:
        """Запускает обработку. Возвращает финальное состояние ParseJob."""
        job = self._jobs.get(parse_job_id)

        # CREATED → QUEUED → RUNNING — state machine честный.
        if job.status == ParseJobStatus.CREATED:
            job.transition_to(ParseJobStatus.QUEUED)
        if job.status == ParseJobStatus.QUEUED:
            job.transition_to(ParseJobStatus.RUNNING)
        else:
            # Уже terminal или уже RUNNING — не переходим повторно.
            pass

        started_at = _now()
        job.started_at = started_at
        job.updated_at = started_at
        self._jobs.update(job)

        self._emit(
            ParseJobStartedEvent(
                event_id=_gen_id("evt"),
                parse_job_id=parse_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=started_at,
                total_documents=job.total_documents,
            )
        )

        succeeded = 0
        failed = 0
        skipped = 0
        total_sections = 0
        low_confidence_total = 0

        for pjd in self._docs.list_for_job(parse_job_id):
            outcome = self._process_document(job=job, doc=pjd)
            if outcome.status == ParseJobDocumentStatus.COMPLETED:
                succeeded += 1
                total_sections += outcome.sections_count
                low_confidence_total += outcome.low_confidence
            elif outcome.status == ParseJobDocumentStatus.FAILED:
                failed += 1
            else:  # SKIPPED
                skipped += 1

        finished_at = _now()
        duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
        job = self._jobs.get(parse_job_id)
        if failed == 0 and skipped == 0 and succeeded == job.total_documents:
            target = ParseJobStatus.COMPLETED
        elif succeeded == 0:
            target = ParseJobStatus.FAILED
        else:
            target = ParseJobStatus.PARTIAL_SUCCESS

        job.transition_to(target)
        job.processed_documents = succeeded
        job.failed_documents = failed
        job.total_sections = total_sections
        job.low_confidence_sections = low_confidence_total
        job.finished_at = finished_at
        job.updated_at = finished_at
        if target == ParseJobStatus.FAILED:
            job.error_code = ParseErrorCode.SECTION_DETECTION_FAILED
            job.error_message = f"All {job.total_documents} documents failed to parse"
        self._jobs.update(job)

        # Финальные events + метрики.
        if target == ParseJobStatus.COMPLETED:
            self._emit(
                ParseJobCompletedEvent(
                    event_id=_gen_id("evt"),
                    parse_job_id=parse_job_id,
                    setup_job_id=job.setup_job_id,
                    occurred_at=finished_at,
                    total_documents=job.total_documents,
                    succeeded=succeeded,
                    failed=failed,
                    skipped=skipped,
                    duration_ms=duration_ms,
                )
            )
        elif target == ParseJobStatus.PARTIAL_SUCCESS:
            self._emit(
                ParseJobPartialSuccessEvent(
                    event_id=_gen_id("evt"),
                    parse_job_id=parse_job_id,
                    setup_job_id=job.setup_job_id,
                    occurred_at=finished_at,
                    succeeded=succeeded,
                    failed=failed,
                    skipped=skipped,
                )
            )
        else:
            self._emit(
                ParseJobFailedEvent(
                    event_id=_gen_id("evt"),
                    parse_job_id=parse_job_id,
                    setup_job_id=job.setup_job_id,
                    occurred_at=finished_at,
                    error_code=(
                        job.error_code.value
                        if job.error_code
                        else ParseErrorCode.SECTION_DETECTION_FAILED.value
                    ),
                    reason=job.error_message or "All documents failed",
                )
            )
        self._inc(
            "parse_jobs_total",
            labels={"outcome": target.value},
            help_text="ParseJob terminal outcomes",
        )
        return job

    # ============================================================
    # Per-document pipeline
    # ============================================================

    def _process_document(self, *, job: ParseJob, doc: ParseJobDocument) -> _DocumentOutcome:
        try:
            source = self._lifecycle._registry.get(doc.source_document_id)
        except Exception as exc:  # noqa: BLE001 — registry raises typed errors
            self._fail_document(
                job=job,
                doc=doc,
                error_code=ParseErrorCode.RAW_FILE_NOT_FOUND,
                reason=f"Source document not found: {exc}",
                strategy=None,
            )
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.FAILED,
                sections_count=0,
                low_confidence=0,
            )

        if source.status not in _PARSEABLE_STATUSES:
            self._skip_document(job=job, doc=doc, source=source)
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.SKIPPED,
                sections_count=0,
                low_confidence=0,
            )

        strategy_enum = self._strategy_for(source)
        if strategy_enum is None:
            self._fail_document(
                job=job,
                doc=doc,
                error_code=ParseErrorCode.UNSUPPORTED_PARSE_FORMAT,
                reason=f"Unsupported content_type {source.content_type!r}",
                strategy=None,
            )
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.FAILED,
                sections_count=0,
                low_confidence=0,
            )

        # Mark PROCESSING.
        started_at = _now()
        doc.status = ParseJobDocumentStatus.PROCESSING
        doc.parser_strategy = strategy_enum
        doc.started_at = started_at
        self._docs.update(doc)
        self._lifecycle.update_status(
            source_document_id=source.source_document_id,
            new_status=SourceDocumentStatus.PARSING,
            event_id=f"{job.parse_job_id}:parsing:{source.source_document_id}",
            reason=f"ParseJob {job.parse_job_id} started",
        )
        self._emit(
            ParseDocumentStartedEvent(
                event_id=_gen_id("evt"),
                parse_job_id=job.parse_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=started_at,
                source_document_id=source.source_document_id,
                strategy=strategy_enum.value,
            )
        )

        perf_start = time.perf_counter()
        try:
            raw = self._storage.download(source.storage_path).data
        except Exception as exc:  # noqa: BLE001 — storage may raise variants
            self._fail_document(
                job=job,
                doc=doc,
                error_code=ParseErrorCode.RAW_FILE_NOT_FOUND,
                reason=f"Failed to fetch raw file: {exc}",
                strategy=strategy_enum,
            )
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.FAILED,
                sections_count=0,
                low_confidence=0,
            )

        try:
            strategy = self._registry.resolve(source.content_type)
            parsed_sections = strategy.parse(
                data=raw,
                source_document_id=source.source_document_id,
                parse_job_id=job.parse_job_id,
                filename=source.filename,
            )
        except UnsupportedFormatError:
            self._fail_document(
                job=job,
                doc=doc,
                error_code=ParseErrorCode.UNSUPPORTED_PARSE_FORMAT,
                reason=f"Unsupported content_type {source.content_type!r}",
                strategy=strategy_enum,
            )
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.FAILED,
                sections_count=0,
                low_confidence=0,
            )
        except ParseFailedError as exc:
            self._fail_document(
                job=job,
                doc=doc,
                error_code=ParseErrorCode(exc.error_code),
                reason=str(exc),
                strategy=strategy_enum,
            )
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.FAILED,
                sections_count=0,
                low_confidence=0,
            )
        except Exception as exc:  # noqa: BLE001 — last-resort safety net
            self._fail_document(
                job=job,
                doc=doc,
                error_code=ParseErrorCode.SECTION_DETECTION_FAILED,
                reason=f"Unexpected parser failure: {exc}",
                strategy=strategy_enum,
            )
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.FAILED,
                sections_count=0,
                low_confidence=0,
            )

        if not parsed_sections:
            self._fail_document(
                job=job,
                doc=doc,
                error_code=ParseErrorCode.SECTION_DETECTION_FAILED,
                reason="Parser returned 0 sections",
                strategy=strategy_enum,
            )
            return _DocumentOutcome(
                status=ParseJobDocumentStatus.FAILED,
                sections_count=0,
                low_confidence=0,
            )

        classified = self._classifier.apply_to_sections(parsed_sections)
        self._sections.save_batch(classified)

        low_confidence = sum(1 for s in classified if (s.confidence or 0) < self._threshold)

        # Lineage + processing log + status.
        for section in classified:
            self._lifecycle.link_artifact(
                source_document_id=source.source_document_id,
                target_type=LineageTargetType.PARSED_SECTION,
                target_id=section.section_id,
                relation_type=LineageRelationType.PARSED_FROM,
                event_id=f"{job.parse_job_id}:lineage:{section.section_id}",
                created_by_service="document_parser_service",
                metadata={"parse_job_id": job.parse_job_id},
            )
            if (section.confidence or 0) < self._threshold:
                self._emit(
                    SectionClassificationLowConfidenceEvent(
                        event_id=_gen_id("evt"),
                        parse_job_id=job.parse_job_id,
                        setup_job_id=job.setup_job_id,
                        occurred_at=_now(),
                        section_id=section.section_id,
                        confidence=section.confidence or 0.0,
                        candidate_type=section.section_type.value,
                    )
                )
            self._inc(
                "parse_sections_total",
                labels={
                    "section_type": section.section_type.value,
                    "confidence_bucket": _confidence_bucket(section.confidence or 0),
                },
                help_text="Parsed sections by type and confidence bucket",
            )

        finished_at = _now()
        duration_ms = max(int((time.perf_counter() - perf_start) * 1000), 0)

        # Update ParseJobDocument.
        doc.status = ParseJobDocumentStatus.COMPLETED
        doc.sections_count = len(classified)
        doc.low_confidence_sections_count = low_confidence
        doc.finished_at = finished_at
        doc.duration_ms = duration_ms
        self._docs.update(doc)

        self._sections.save_batch  # for static checker happiness  # noqa: B018

        # Report.
        sections_by_type: Counter[str] = Counter(s.section_type.value for s in classified)
        report = DocumentParseReport(
            parse_report_id=_gen_id("pr"),
            parse_job_id=job.parse_job_id,
            source_document_id=source.source_document_id,
            status=ParseJobDocumentStatus.COMPLETED,
            parser_strategy=strategy_enum,
            summary=SectionsSummary(
                sections_count=len(classified),
                sections_by_type=dict(sections_by_type),
                low_confidence_sections=low_confidence,
            ),
            errors=[],
            warnings=(
                [{"code": "LOW_CONFIDENCE", "count": low_confidence}] if low_confidence else []
            ),
            created_at=finished_at,
        )
        self._reports.save(report)

        # Source status → SECTIONS_EXTRACTED.
        self._lifecycle.update_status(
            source_document_id=source.source_document_id,
            new_status=SourceDocumentStatus.SECTIONS_EXTRACTED,
            event_id=f"{job.parse_job_id}:done:{source.source_document_id}",
            reason=f"ParseJob {job.parse_job_id} succeeded",
        )
        self._lifecycle.append_processing_log(
            source_document_id=source.source_document_id,
            setup_job_id=job.setup_job_id,
            step=ProcessingLogStep.PARSING,
            message=(f"Parsed {len(classified)} sections via {strategy_enum.value}"),
            event_id=f"{job.parse_job_id}:log:{source.source_document_id}",
            level=ProcessingLogLevel.INFO,
            payload={
                "parse_job_id": job.parse_job_id,
                "strategy": strategy_enum.value,
                "sections_count": len(classified),
                "low_confidence_sections": low_confidence,
                "duration_ms": duration_ms,
            },
        )

        self._emit(
            ParsedSectionsCreatedEvent(
                event_id=_gen_id("evt"),
                parse_job_id=job.parse_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=finished_at,
                source_document_id=source.source_document_id,
                section_ids=[s.section_id for s in classified],
                sections_count=len(classified),
            )
        )
        self._emit(
            ParseDocumentCompletedEvent(
                event_id=_gen_id("evt"),
                parse_job_id=job.parse_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=finished_at,
                source_document_id=source.source_document_id,
                sections_count=len(classified),
                duration_ms=duration_ms,
            )
        )
        self._inc(
            "parse_documents_total",
            labels={"format": strategy_enum.value, "outcome": "completed"},
            help_text="Parsed documents by format and outcome",
        )
        self._observe(
            "parse_duration_seconds",
            value=duration_ms / 1000.0,
            labels={"format": strategy_enum.value},
            help_text="Document parse duration (seconds)",
        )
        return _DocumentOutcome(
            status=ParseJobDocumentStatus.COMPLETED,
            sections_count=len(classified),
            low_confidence=low_confidence,
        )

    # ============================================================
    # Helpers
    # ============================================================

    def _strategy_for(self, source: SourceDocument) -> ParserStrategyEnum | None:
        try:
            return self._registry.strategy_enum_for(source.content_type)
        except UnsupportedFormatError:
            return None

    def _eligible_documents(self, setup_job_id: str) -> list[SourceDocument]:
        documents = self._lifecycle._registry.list_for_job(setup_job_id)
        return [d for d in documents if d.status in _PARSEABLE_STATUSES]

    def _fail_document(
        self,
        *,
        job: ParseJob,
        doc: ParseJobDocument,
        error_code: ParseErrorCode,
        reason: str,
        strategy: ParserStrategyEnum | None,
    ) -> None:
        finished_at = _now()
        doc.status = ParseJobDocumentStatus.FAILED
        if strategy is not None:
            doc.parser_strategy = strategy
        doc.finished_at = finished_at
        doc.error_code = error_code
        doc.error_message = reason
        if doc.started_at is not None:
            doc.duration_ms = max(int((finished_at - doc.started_at).total_seconds() * 1000), 0)
        self._docs.update(doc)

        report = DocumentParseReport(
            parse_report_id=_gen_id("pr"),
            parse_job_id=job.parse_job_id,
            source_document_id=doc.source_document_id,
            status=ParseJobDocumentStatus.FAILED,
            parser_strategy=strategy,
            summary=SectionsSummary(
                sections_count=0, sections_by_type={}, low_confidence_sections=0
            ),
            errors=[{"code": error_code.value, "message": reason}],
            warnings=[],
            created_at=finished_at,
        )
        self._reports.save(report)

        # Lifecycle: PARSE_FAILED + ERROR log. Если статус ещё не PARSING
        # (например failed на этапе RAW_FILE_NOT_FOUND), переход недопустим —
        # это нормально: запись об ошибке всё равно появится в processing log.
        with contextlib.suppress(Exception):
            self._lifecycle.update_status(
                source_document_id=doc.source_document_id,
                new_status=SourceDocumentStatus.PARSE_FAILED,
                event_id=f"{job.parse_job_id}:fail:{doc.source_document_id}",
                reason=reason[:255],
            )
        self._lifecycle.append_processing_log(
            source_document_id=doc.source_document_id,
            setup_job_id=job.setup_job_id,
            step=ProcessingLogStep.PARSING,
            message=reason,
            event_id=f"{job.parse_job_id}:errlog:{doc.source_document_id}",
            level=ProcessingLogLevel.ERROR,
            error_code=error_code.value,
            payload={"parse_job_id": job.parse_job_id},
        )

        self._emit(
            ParseDocumentFailedEvent(
                event_id=_gen_id("evt"),
                parse_job_id=job.parse_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=finished_at,
                source_document_id=doc.source_document_id,
                error_code=error_code.value,
                reason=reason,
            )
        )
        self._inc(
            "parse_documents_total",
            labels={
                "format": strategy.value if strategy else "unknown",
                "outcome": "failed",
            },
            help_text="Parsed documents by format and outcome",
        )
        self._inc(
            "parse_job_failures_total",
            labels={"error_code": error_code.value},
            help_text="ParseJob document failures by error_code",
        )

    def _skip_document(
        self,
        *,
        job: ParseJob,
        doc: ParseJobDocument,
        source: SourceDocument,
    ) -> None:
        finished_at = _now()
        doc.status = ParseJobDocumentStatus.SKIPPED
        doc.finished_at = finished_at
        doc.error_code = ParseErrorCode.DOCUMENT_NOT_PARSEABLE_STATUS
        doc.error_message = f"Document status {source.status.value} is not parseable"
        self._docs.update(doc)

        report = DocumentParseReport(
            parse_report_id=_gen_id("pr"),
            parse_job_id=job.parse_job_id,
            source_document_id=source.source_document_id,
            status=ParseJobDocumentStatus.SKIPPED,
            parser_strategy=None,
            summary=SectionsSummary(
                sections_count=0, sections_by_type={}, low_confidence_sections=0
            ),
            errors=[],
            warnings=[
                {
                    "code": "SKIPPED",
                    "reason": f"status={source.status.value} not parseable",
                }
            ],
            created_at=finished_at,
        )
        self._reports.save(report)

        self._lifecycle.append_processing_log(
            source_document_id=source.source_document_id,
            setup_job_id=job.setup_job_id,
            step=ProcessingLogStep.PARSING,
            message=f"Skipped: status={source.status.value}",
            event_id=f"{job.parse_job_id}:skiplog:{source.source_document_id}",
            level=ProcessingLogLevel.WARNING,
            payload={"parse_job_id": job.parse_job_id},
        )

    # --- side-effect adapters ---

    def _emit(self, event: _BaseParseEvent) -> None:
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
        target_type: str,
        target_id: str,
        setup_job_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            setup_job_id=setup_job_id,
            payload=payload or {},
        )

    def _inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(name, labels=labels, help_text=help_text)

    def _observe(
        self,
        name: str,
        *,
        value: float,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        if self._metrics is None:
            return
        # MetricsRegistry в MVP не различает гистограммы и счётчики — но
        # сохраним сэмплы как отдельную метрику через observe-like API
        # (fallback: inc, чтобы тесты могли увидеть факт регистрации).
        observe = getattr(self._metrics, "observe", None)
        if observe is not None:
            observe(name, value=value, labels=labels, help_text=help_text)
        else:  # pragma: no cover — MVP fallback
            self._metrics.inc(name, labels=labels, help_text=help_text)


# ----- internal value -----


class _DocumentOutcome:
    __slots__ = ("status", "sections_count", "low_confidence")

    def __init__(
        self,
        *,
        status: ParseJobDocumentStatus,
        sections_count: int,
        low_confidence: int,
    ) -> None:
        self.status = status
        self.sections_count = sections_count
        self.low_confidence = low_confidence
