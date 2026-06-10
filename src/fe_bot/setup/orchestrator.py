"""Setup Orchestrator (SVC-04) — управление lifecycle setup job.

S1 acceptance:
- 13 шагов state machine (закодированы в RAGSetupJob.transition_to из S0).
- Каждый переход эмитит SetupProgressEvent.
- Создание / получение / отмена job.

**Что отложено:**
- Реальная LangGraph-обёртка вокруг state machine (до S3, когда появятся
  реальные имплементации шагов parse/generate/etc.). State-логика уже
  централизована в RAGSetupJob.transition_to(), переход на LangGraph
  будет drop-in.
- PostgreSQL checkpointer для resume-after-crash (до INF-002).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from schemas.setup.rag_setup_job import (
    InvalidTransitionError,
    RAGSetupJob,
    SetupJobStatus,
)

from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.repository import JobRepository

# Удельная доля прогресса на каждый статус. Сумма = 100.
_PROGRESS_PER_STATUS: dict[SetupJobStatus, float] = {
    SetupJobStatus.DRAFT: 0.0,
    SetupJobStatus.FILES_UPLOADED: 5.0,
    SetupJobStatus.PARSING: 15.0,
    SetupJobStatus.SECTIONS_EXTRACTED: 25.0,
    SetupJobStatus.RAG_CARDS_GENERATING: 40.0,
    SetupJobStatus.METADATA_VALIDATING: 50.0,
    SetupJobStatus.REVIEW_REQUIRED: 55.0,
    SetupJobStatus.CHUNKING: 65.0,
    SetupJobStatus.EMBEDDING: 78.0,
    SetupJobStatus.INDEXING: 88.0,
    SetupJobStatus.RETRIEVAL_TESTING: 94.0,
    SetupJobStatus.PUBLISHING: 98.0,
    SetupJobStatus.READY: 100.0,
    SetupJobStatus.FAILED: 0.0,
    SetupJobStatus.CANCELLED: 0.0,
}


class SetupOrchestrator:
    """Сервис управления setup job (T-S01-008)."""

    def __init__(self, repository: JobRepository, event_bus: EventBus) -> None:
        self._repo = repository
        self._bus = event_bus

    def create_job(
        self,
        *,
        user_id: str,
        project_name: str,
    ) -> RAGSetupJob:
        """Создаёт новый job в статусе DRAFT и эмитит setup.job.created."""
        setup_job_id = f"setup_{uuid.uuid4().hex[:12]}"
        job = RAGSetupJob(
            setup_job_id=setup_job_id,
            user_id=user_id,
            project_name=project_name,
            status=SetupJobStatus.DRAFT,
            progress_percent=0.0,
            error_count=0,
            warning_count=0,
            started_at=datetime.now(tz=UTC),
        )
        self._repo.save(job)
        self._bus.publish(
            SetupProgressEvent(
                event_type="setup.job.created",
                setup_job_id=setup_job_id,
                status="created",
                progress_percent=0.0,
                message=f"Setup job {setup_job_id} created",
            )
        )
        return job

    def get_job(self, setup_job_id: str) -> RAGSetupJob:
        """Возвращает job (бросает JobNotFoundError)."""
        return self._repo.get(setup_job_id)

    def advance(
        self,
        setup_job_id: str,
        new_status: SetupJobStatus,
        *,
        message: str | None = None,
        metrics: dict[str, object] | None = None,
    ) -> RAGSetupJob:
        """Переводит job в new_status и эмитит соответствующее событие.

        Raises:
            InvalidTransitionError: невалидный переход (см. S0).
            JobNotFoundError: job не существует.
        """
        job = self._repo.get(setup_job_id)
        job.transition_to(new_status)
        job.progress_percent = _PROGRESS_PER_STATUS[new_status]
        job.current_step = new_status.value
        if new_status in {SetupJobStatus.READY, SetupJobStatus.FAILED, SetupJobStatus.CANCELLED}:
            job.finished_at = datetime.now(tz=UTC)
        self._repo.save(job)

        event_type = _event_type_for(new_status)
        self._bus.publish(
            SetupProgressEvent(
                event_type=event_type,
                setup_job_id=setup_job_id,
                step=new_status,
                status=_event_status_label(new_status),
                progress_percent=job.progress_percent,
                message=message,
                metrics=metrics or {},
            )
        )
        return job

    def cancel_job(self, setup_job_id: str) -> RAGSetupJob:
        """Отменяет job. Идемпотентна для уже отменённых."""
        job = self._repo.get(setup_job_id)
        if job.status == SetupJobStatus.CANCELLED:
            return job  # идемпотентная отмена
        try:
            return self.advance(setup_job_id, SetupJobStatus.CANCELLED, message="Cancelled by user")
        except InvalidTransitionError as exc:
            # ready → cancelled разрешён по правилам; всё остальное допустимо.
            # Если по какой-то причине нет — пробрасываем.
            raise exc


def _event_type_for(status: SetupJobStatus) -> str:
    if status == SetupJobStatus.READY:
        return "setup.kb.ready"
    if status == SetupJobStatus.FAILED:
        return "setup.step.failed"
    if status == SetupJobStatus.CANCELLED:
        return "setup.job.cancelled"
    if status == SetupJobStatus.REVIEW_REQUIRED:
        return "setup.review.required"
    return "setup.step.started"


def _event_status_label(status: SetupJobStatus) -> str:
    if status == SetupJobStatus.READY:
        return "completed"
    if status in {SetupJobStatus.FAILED, SetupJobStatus.CANCELLED}:
        return status.value
    return "in_progress"
