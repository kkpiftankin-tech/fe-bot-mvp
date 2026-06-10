"""Document Upload Service (SVC-05 + T-S02-011/012/013 audit/metrics/logging).

Принимает файл, валидирует, считает SHA-256, сохраняет в Artifact Storage,
регистрирует в Source Registry и (при необходимости) продвигает Setup Job
из DRAFT в FILES_UPLOADED. Дедуп по checksum даёт варианты: skip / replace / new_version.

T-S02-011: emits AuditEvent: DOCUMENT_UPLOADED / DOCUMENT_REJECTED /
DOCUMENT_DUPLICATE_SKIPPED / DOCUMENT_REPLACED.
T-S02-012: emits Counter/Histogram metrics: upload_files_total, upload_bytes_total,
upload_errors_total, upload_latency_seconds, upload_file_size_bytes.
T-S02-013: structured logging с correlation_id (через contextvars middleware).

Source of truth — docs/02-system/features/SETUP-01-setup-wizard.md §7.2 A1, §18.1,
docs/02-system/features/SETUP-02-document-upload.md §11.1,
docs/implementation-plan/SETUP-01.tasks.md T-S01-012,
docs/implementation-plan/SETUP-02.tasks.md T-S02-011..013.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from schemas.setup.rag_setup_job import SetupJobStatus
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus

from fe_bot.audit.service import AuditAction, AuditOutcome, AuditService
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.repository import JobRepository
from fe_bot.setup.source_registry.service import (
    DuplicateDocumentError,
    SourceRegistry,
)
from fe_bot.setup.upload.validation import UploadValidationError, validate_file
from fe_bot.storage.artifact_service import ArtifactStorage

logger = logging.getLogger(__name__)


class DuplicateStrategy(StrEnum):
    SKIP = "skip"
    REPLACE = "replace"
    NEW_VERSION = "new_version"


@dataclass(frozen=True, slots=True)
class UploadResult:
    document: SourceDocument
    was_duplicate: bool  # true если попал в существующий через skip


class JobNotAcceptingUploadsError(ValueError):
    """Setup job в статусе, не допускающем загрузку (running/ready/cancelled)."""

    def __init__(self, setup_job_id: str, status: SetupJobStatus) -> None:
        self.setup_job_id = setup_job_id
        self.status = status
        super().__init__(
            f"Setup job {setup_job_id} in status {status.value!r} does not accept uploads"
        )


_UPLOAD_ALLOWED_STATUSES = frozenset(
    {SetupJobStatus.DRAFT, SetupJobStatus.FILES_UPLOADED}
)


class DocumentUploadService:
    """Сервис загрузки документов (SVC-05).

    T-S02-011/012: опциональные audit_service + metrics. Если не переданы —
    сервис работает как раньше (без observability). В продакшене обязательны.
    """

    def __init__(
        self,
        *,
        job_repository: JobRepository,
        source_registry: SourceRegistry,
        artifact_storage: ArtifactStorage,
        event_bus: EventBus,
        audit_service: AuditService | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._jobs = job_repository
        self._registry = source_registry
        self._storage = artifact_storage
        self._bus = event_bus
        self._audit = audit_service
        self._metrics = metrics

    def upload(
        self,
        *,
        setup_job_id: str,
        filename: str,
        content_type: str,
        data: bytes,
        uploaded_by: str,
        duplicate_strategy: DuplicateStrategy = DuplicateStrategy.SKIP,
    ) -> UploadResult:
        """Загружает один файл.

        Raises:
            JobNotAcceptingUploadsError: если job нельзя расширять.
            UploadValidationError: если файл не проходит валидацию.
            DuplicateDocumentError: если стратегия NEW_VERSION требует уникальности,
                но checksum уже зарегистрирован (защита от логической ошибки клиента).
        """
        size_bytes = len(data)
        total_start = time.perf_counter()
        log_extra = {
            "setup_job_id": setup_job_id,
            "doc_filename": filename,
            "size_bytes": size_bytes,
            "duplicate_strategy": duplicate_strategy.value,
        }

        job = self._jobs.get(setup_job_id)
        if job.status not in _UPLOAD_ALLOWED_STATUSES:
            raise JobNotAcceptingUploadsError(setup_job_id, job.status)

        # T-S02-013: structured logging start.
        logger.info("upload.started", extra=log_extra)

        # T-S02-012: per-phase histograms.
        validation_start = time.perf_counter()
        try:
            validate_file(
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
            )
        except UploadValidationError as exc:
            self._record_validation_latency(validation_start)
            self._emit_rejected(
                setup_job_id=setup_job_id,
                filename=filename,
                size_bytes=size_bytes,
                uploaded_by=uploaded_by,
                error_code=exc.code.value,
                error_message=str(exc),
            )
            raise
        self._record_validation_latency(validation_start)

        checksum_start = time.perf_counter()
        checksum = hashlib.sha256(data).hexdigest()
        self._observe(
            "upload_latency_seconds",
            time.perf_counter() - checksum_start,
            labels={"phase": "checksum"},
        )

        existing = self._registry.find_by_checksum(setup_job_id, checksum)
        if existing is not None:
            if duplicate_strategy == DuplicateStrategy.SKIP:
                self._emit_duplicate_skipped(
                    setup_job_id=setup_job_id,
                    filename=filename,
                    size_bytes=size_bytes,
                    uploaded_by=uploaded_by,
                    existing_doc_id=existing.source_document_id,
                    checksum=checksum,
                )
                logger.info(
                    "upload.duplicate_skipped",
                    extra={**log_extra, "existing_doc_id": existing.source_document_id},
                )
                self._observe_total_latency(total_start)
                return UploadResult(document=existing, was_duplicate=True)
            if duplicate_strategy == DuplicateStrategy.REPLACE:
                # Удаляем старый объект и регистрируем новый с тем же checksum.
                self._storage.delete(existing.storage_path)
                # Source Registry не позволяет менять checksum, поэтому удаляем запись
                # и регистрируем заново под новым source_document_id.
                self._registry.update(
                    existing.model_copy(update={"status": SourceDocumentStatus.ARCHIVED})
                )
                self._emit_replaced(
                    setup_job_id=setup_job_id,
                    filename=filename,
                    uploaded_by=uploaded_by,
                    replaced_doc_id=existing.source_document_id,
                )
            # NEW_VERSION падает на add() ниже с DuplicateDocumentError — это корректно.

        source_document_id = f"src_{uuid.uuid4().hex[:12]}"

        storage_phase_start = time.perf_counter()
        storage_path = self._storage.upload(
            setup_job_id=setup_job_id,
            source_document_id=source_document_id,
            filename=filename,
            content_type=content_type,
            data=data,
        )
        self._observe(
            "upload_latency_seconds",
            time.perf_counter() - storage_phase_start,
            labels={"phase": "storage"},
        )

        document = SourceDocument(
            source_document_id=source_document_id,
            setup_job_id=setup_job_id,
            filename=filename,
            content_type=content_type,
            storage_path=storage_path,
            size_bytes=size_bytes,
            checksum=checksum,
            status=SourceDocumentStatus.UPLOADED,
            detected_language=None,
            document_kind=None,
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(tz=UTC),
            parsed_at=None,
            error_message=None,
        )
        registry_start = time.perf_counter()
        try:
            self._registry.add(document)
        except DuplicateDocumentError:
            # Это не должно произойти после find_by_checksum + replace/skip,
            # но если NEW_VERSION выбран и checksum совпал — пробрасываем дальше.
            self._storage.delete(storage_path)
            raise
        self._observe(
            "upload_latency_seconds",
            time.perf_counter() - registry_start,
            labels={"phase": "registry"},
        )

        # Продвигаем job draft → files_uploaded только на первой загрузке.
        if job.status == SetupJobStatus.DRAFT:
            job.transition_to(SetupJobStatus.FILES_UPLOADED)
            job.source_document_ids.append(source_document_id)
            self._jobs.save(job)
        else:
            job.source_document_ids.append(source_document_id)
            self._jobs.save(job)

        self._bus.publish(
            SetupProgressEvent(
                event_type="setup.document.uploaded",
                setup_job_id=setup_job_id,
                step=SetupJobStatus.FILES_UPLOADED,
                status="in_progress",
                progress_percent=5.0,
                message=f"Uploaded {filename}",
                metrics={
                    "source_document_id": source_document_id,
                    "size_bytes": size_bytes,
                },
            )
        )

        # T-S02-011/012/013: observability hooks.
        self._emit_uploaded(
            setup_job_id=setup_job_id,
            source_document_id=source_document_id,
            filename=filename,
            size_bytes=size_bytes,
            uploaded_by=uploaded_by,
            checksum=checksum,
        )
        logger.info(
            "upload.completed",
            extra={
                **log_extra,
                "source_document_id": source_document_id,
                "checksum": checksum[:12],
            },
        )
        self._observe_total_latency(total_start)
        return UploadResult(document=document, was_duplicate=False)

    def remove_document(
        self,
        *,
        setup_job_id: str,
        source_document_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> SourceDocument:
        """T-S02-014: soft-delete документа.

        Гарантии:
        - Только если job в DRAFT/FILES_UPLOADED (иначе JobNotAcceptingUploadsError).
        - Только если документ принадлежит этому setup_job_id (иначе
          SourceDocumentNotFoundError — защита от cross-job lookup).
        - Идемпотентно: повторный DELETE того же документа возвращает уже-removed
          без ошибки.
        - Физически удаляет объект из storage; запись в registry помечается REMOVED.
        - Releases дедуп-ключ → можно загрузить тот же файл повторно.
        - Удаляет source_document_id из job.source_document_ids.
        - Audit + Metrics (DOCUMENT_REMOVED + upload_files_total{outcome=removed}).
        """
        from fe_bot.setup.source_registry.service import (
            SourceDocumentNotFoundError,
        )

        job = self._jobs.get(setup_job_id)
        if job.status not in _UPLOAD_ALLOWED_STATUSES:
            raise JobNotAcceptingUploadsError(setup_job_id, job.status)

        # Cross-job protection: документ должен принадлежать этому job.
        document = self._registry.get(source_document_id)
        if document.setup_job_id != setup_job_id:
            raise SourceDocumentNotFoundError(source_document_id)

        already_removed = document.status == SourceDocumentStatus.REMOVED

        removed = self._registry.remove(source_document_id)

        if not already_removed:
            # Физически удаляем объект из storage.
            with contextlib.suppress(Exception):
                self._storage.delete(document.storage_path)

            # Убираем id из job.source_document_ids.
            if source_document_id in job.source_document_ids:
                job.source_document_ids.remove(source_document_id)
                self._jobs.save(job)

            self._emit_removed(
                setup_job_id=setup_job_id,
                source_document_id=source_document_id,
                filename=document.filename,
                size_bytes=document.size_bytes,
                actor_id=actor_id,
                reason=reason,
            )
            logger.info(
                "document.removed",
                extra={
                    "setup_job_id": setup_job_id,
                    "source_document_id": source_document_id,
                    "doc_filename": document.filename,
                    "reason": reason,
                },
            )

        return removed

    # ------------ T-S02-011/012/013 observability helpers ------------

    def _emit_uploaded(
        self,
        *,
        setup_job_id: str,
        source_document_id: str,
        filename: str,
        size_bytes: int,
        uploaded_by: str,
        checksum: str,
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                actor_id=uploaded_by,
                action=AuditAction.DOCUMENT_UPLOADED,
                target_type="source_document",
                target_id=source_document_id,
                setup_job_id=setup_job_id,
                payload={
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "checksum": checksum,
                },
            )
        self._inc(
            "upload_files_total",
            labels={"outcome": "uploaded"},
            help_text="Per-file upload outcome counts",
        )
        self._inc(
            "upload_bytes_total",
            labels={"outcome": "uploaded"},
            value=float(size_bytes),
            help_text="Total bytes by upload outcome",
        )
        self._observe(
            "upload_file_size_bytes",
            float(size_bytes),
            help_text="Histogram of accepted file sizes",
        )

    def _emit_rejected(
        self,
        *,
        setup_job_id: str,
        filename: str,
        size_bytes: int,
        uploaded_by: str,
        error_code: str,
        error_message: str,
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                actor_id=uploaded_by,
                action=AuditAction.DOCUMENT_REJECTED,
                target_type="source_document",
                target_id=filename or "unknown",
                setup_job_id=setup_job_id,
                outcome=AuditOutcome.FAILURE,
                payload={
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )
        self._inc("upload_files_total", labels={"outcome": "rejected"})
        self._inc("upload_bytes_total", labels={"outcome": "rejected"}, value=float(size_bytes))
        self._inc("upload_errors_total", labels={"error_code": error_code})
        logger.warning(
            "upload.rejected",
            extra={
                "setup_job_id": setup_job_id,
                "doc_filename": filename,
                "error_code": error_code,
            },
        )

    def _emit_duplicate_skipped(
        self,
        *,
        setup_job_id: str,
        filename: str,
        size_bytes: int,
        uploaded_by: str,
        existing_doc_id: str,
        checksum: str,
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                actor_id=uploaded_by,
                action=AuditAction.DOCUMENT_DUPLICATE_SKIPPED,
                target_type="source_document",
                target_id=existing_doc_id,
                setup_job_id=setup_job_id,
                payload={
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "checksum": checksum,
                    "existing_doc_id": existing_doc_id,
                },
            )
        self._inc("upload_files_total", labels={"outcome": "duplicate"})
        self._inc(
            "upload_bytes_total", labels={"outcome": "duplicate"}, value=float(size_bytes)
        )

    def _emit_replaced(
        self,
        *,
        setup_job_id: str,
        filename: str,
        uploaded_by: str,
        replaced_doc_id: str,
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                actor_id=uploaded_by,
                action=AuditAction.DOCUMENT_REPLACED,
                target_type="source_document",
                target_id=replaced_doc_id,
                setup_job_id=setup_job_id,
                payload={"filename": filename, "replaced_doc_id": replaced_doc_id},
            )
        self._inc("upload_files_total", labels={"outcome": "replaced"})

    def _emit_removed(
        self,
        *,
        setup_job_id: str,
        source_document_id: str,
        filename: str,
        size_bytes: int,
        actor_id: str,
        reason: str | None,
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                actor_id=actor_id,
                action=AuditAction.DOCUMENT_REMOVED,
                target_type="source_document",
                target_id=source_document_id,
                setup_job_id=setup_job_id,
                payload={
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "reason": reason,
                },
            )
        self._inc(
            "upload_files_total",
            labels={"outcome": "removed"},
            help_text="Per-file upload outcome counts",
        )

    def _record_validation_latency(self, start: float) -> None:
        self._observe(
            "upload_latency_seconds",
            time.perf_counter() - start,
            labels={"phase": "validation"},
        )

    def _observe_total_latency(self, start: float) -> None:
        self._observe(
            "upload_latency_seconds",
            time.perf_counter() - start,
            labels={"phase": "total"},
        )

    def _inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
        help_text: str = "",
    ) -> None:
        if self._metrics is not None:
            self._metrics.inc(name, labels=labels, value=value, help_text=help_text)

    def _observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        if self._metrics is not None:
            self._metrics.observe(name, value, labels=labels, help_text=help_text)
