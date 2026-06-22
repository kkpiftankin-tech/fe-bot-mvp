"""Audit Service (T-S01-048).

Структура AuditEvent (≈ DTO-49):
- event_id: UUID
- timestamp: UTC
- actor_id: кто инициировал (user_id / "system")
- action: семантическое имя (`job.created`, `card.approved`, `kb.published`)
- target_type: тип ресурса (`setup_job`, `rag_card`, `kb_version`, ...)
- target_id: id ресурса
- setup_job_id: scope (опционально — для cross-cutting actions, например, audit логин/логаут)
- outcome: `success` | `failure` | `denied`
- payload: дополнительные структурированные поля

Хранится в InMemoryAuditLog; PostgreSQL append-only log — INF-006.

Invariants:
- AuditEvent **иммутабелен** после записи (frozen=True).
- Логи **не удаляются** (только архивируются вне MVP).
- Любая попытка фильтрации/чтения сама генерирует audit-event типа `audit.read`
  (запрещено в MVP — добавляется в S8+).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class AuditAction(StrEnum):
    # Setup job lifecycle
    JOB_CREATED = "job.created"
    JOB_CANCELLED = "job.cancelled"
    JOB_FAILED = "job.failed"
    JOB_READY = "job.ready"

    # Documents
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_REJECTED = "document.rejected"  # T-S02-011: per-file validation failure
    DOCUMENT_DUPLICATE_SKIPPED = "document.duplicate_skipped"
    DOCUMENT_REPLACED = "document.replaced"  # T-S02-011: для DuplicateStrategy.REPLACE
    DOCUMENT_REMOVED = "document.removed"  # T-S02-011: для DELETE (S4)
    BATCH_COMPLETED = "batch.completed"  # T-S02-011: финализация batch

    # SETUP-03 / T-S03-022: Source Registry lifecycle actions.
    STATUS_CHANGED = "source.status_changed"
    METADATA_UPDATED = "source.metadata_updated"
    LINEAGE_ADDED = "source.lineage_added"
    PROCESSING_RETRY_TRIGGERED = "source.retry_triggered"

    # Pipeline
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_STEP_COMPLETED = "pipeline.step_completed"
    PIPELINE_STEP_FAILED = "pipeline.step_failed"

    # Cards / Review
    CARD_GENERATED = "card.generated"
    CARD_VALIDATION_PASSED = "card.validation_passed"
    CARD_VALIDATION_FAILED = "card.validation_failed"
    CARD_REVIEW_APPROVED = "card.review_approved"
    CARD_REVIEW_REJECTED = "card.review_rejected"
    CARD_REVIEW_EDITED = "card.review_edited"
    CARD_REVIEW_REGENERATED = "card.review_regenerated"

    # SETUP-05 / T-S05-039: RAG card generation audit actions.
    RAG_CARD_GENERATION_TRIGGERED = "rag_card.generation_triggered"
    RAG_CARD_GENERATED = "rag_card.generated"
    RAG_CARD_REGENERATE_TRIGGERED = "rag_card.regenerate_triggered"
    RAG_CARD_REVIEW_REQUIRED = "rag_card.review_required"
    RAG_CARD_GENERATION_CANCELLED = "rag_card.generation_cancelled"

    # Indexing
    CHUNKS_INDEXED = "chunks.indexed"
    INDEX_FAILED = "index.failed"

    # Eval
    RETRIEVAL_TEST_PASSED = "retrieval.test_passed"
    RETRIEVAL_TEST_FAILED = "retrieval.test_failed"

    # KB
    KB_PUBLISHED = "kb.published"
    KB_DEPRECATED = "kb.deprecated"

    # Auth
    ACCESS_DENIED = "access.denied"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditEvent(BaseModel):
    """Запись аудита (immutable)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    actor_id: str = Field(..., min_length=1, max_length=128)
    action: AuditAction
    target_type: str = Field(..., min_length=1, max_length=64)
    target_id: str = Field(..., min_length=1, max_length=256)
    setup_job_id: str | None = None
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...

    def list_for_job(self, setup_job_id: str) -> list[AuditEvent]: ...

    def list_for_actor(self, actor_id: str) -> list[AuditEvent]: ...

    def list_recent(self, limit: int = 100) -> list[AuditEvent]: ...


class InMemoryAuditLog:
    """In-memory append-only audit log.

    list_* возвращают копии (защита от случайной мутации).
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def list_for_job(self, setup_job_id: str) -> list[AuditEvent]:
        return [e.model_copy(deep=True) for e in self._events if e.setup_job_id == setup_job_id]

    def list_for_actor(self, actor_id: str) -> list[AuditEvent]:
        return [e.model_copy(deep=True) for e in self._events if e.actor_id == actor_id]

    def list_recent(self, limit: int = 100) -> list[AuditEvent]:
        # Возвращаем последние `limit` в обратном хронологическом порядке.
        return [e.model_copy(deep=True) for e in reversed(self._events[-limit:])]

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        """Только для тестов."""
        self._events.clear()


class AuditService:
    """Удобный высокоуровневый API над AuditRepository."""

    def __init__(self, repository: AuditRepository) -> None:
        self._repo = repository

    def record(
        self,
        *,
        actor_id: str,
        action: AuditAction,
        target_type: str,
        target_id: str,
        setup_job_id: str | None = None,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            setup_job_id=setup_job_id,
            outcome=outcome,
            payload=payload or {},
        )
        self._repo.append(event)
        return event
