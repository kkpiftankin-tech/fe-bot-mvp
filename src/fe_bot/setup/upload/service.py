"""Document Upload Service (SVC-05).

Принимает файл, валидирует, считает SHA-256, сохраняет в Artifact Storage,
регистрирует в Source Registry и (при необходимости) продвигает Setup Job
из DRAFT в FILES_UPLOADED. Дедуп по checksum даёт варианты: skip / replace / new_version.

Source of truth — docs/02-system/features/SETUP-01-setup-wizard.md §7.2 A1, §18.1,
docs/implementation-plan/SETUP-01.tasks.md T-S01-012.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from schemas.setup.rag_setup_job import SetupJobStatus
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus

from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.repository import JobRepository
from fe_bot.setup.source_registry.service import (
    DuplicateDocumentError,
    SourceRegistry,
)
from fe_bot.setup.upload.validation import validate_file
from fe_bot.storage.artifact_service import ArtifactStorage


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
    """Сервис загрузки документов (SVC-05)."""

    def __init__(
        self,
        *,
        job_repository: JobRepository,
        source_registry: SourceRegistry,
        artifact_storage: ArtifactStorage,
        event_bus: EventBus,
    ) -> None:
        self._jobs = job_repository
        self._registry = source_registry
        self._storage = artifact_storage
        self._bus = event_bus

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
        job = self._jobs.get(setup_job_id)
        if job.status not in _UPLOAD_ALLOWED_STATUSES:
            raise JobNotAcceptingUploadsError(setup_job_id, job.status)

        size_bytes = len(data)
        validate_file(
            filename=filename, content_type=content_type, size_bytes=size_bytes
        )
        checksum = hashlib.sha256(data).hexdigest()

        existing = self._registry.find_by_checksum(setup_job_id, checksum)
        if existing is not None:
            if duplicate_strategy == DuplicateStrategy.SKIP:
                return UploadResult(document=existing, was_duplicate=True)
            if duplicate_strategy == DuplicateStrategy.REPLACE:
                # Удаляем старый объект и регистрируем новый с тем же checksum.
                self._storage.delete(existing.storage_path)
                # Source Registry не позволяет менять checksum, поэтому удаляем запись
                # и регистрируем заново под новым source_document_id.
                # Для MVP достаточно: реальный replace через update PostgreSQL появится в INF-002.
                self._registry.update(
                    existing.model_copy(update={"status": SourceDocumentStatus.ARCHIVED})
                )
            # NEW_VERSION падает на add() ниже с DuplicateDocumentError — это корректно.

        source_document_id = f"src_{uuid.uuid4().hex[:12]}"
        storage_path = self._storage.upload(
            setup_job_id=setup_job_id,
            source_document_id=source_document_id,
            filename=filename,
            content_type=content_type,
            data=data,
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
        try:
            self._registry.add(document)
        except DuplicateDocumentError:
            # Это не должно произойти после find_by_checksum + replace/skip,
            # но если NEW_VERSION выбран и checksum совпал — пробрасываем дальше.
            self._storage.delete(storage_path)
            raise

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
        return UploadResult(document=document, was_duplicate=False)
