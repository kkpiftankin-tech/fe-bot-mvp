"""KnowledgeBaseVersionDTO (DTO-17) — опубликованная/готовящаяся версия KB.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-17,
docs/06-rag/rag-lifecycle.md (immutability after active).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KBStatus(StrEnum):
    DRAFT = "draft"
    TESTING = "testing"
    READY = "ready"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FAILED = "failed"


_KB_TRANSITIONS: dict[KBStatus, frozenset[KBStatus]] = {
    KBStatus.DRAFT: frozenset({KBStatus.TESTING, KBStatus.FAILED}),
    KBStatus.TESTING: frozenset({KBStatus.READY, KBStatus.FAILED, KBStatus.DRAFT}),
    KBStatus.READY: frozenset({KBStatus.ACTIVE, KBStatus.DEPRECATED, KBStatus.FAILED}),
    # ACTIVE — иммутабельна; следующий шаг только deprecation (после публикации новой active).
    KBStatus.ACTIVE: frozenset({KBStatus.DEPRECATED}),
    KBStatus.DEPRECATED: frozenset(),  # terminal
    KBStatus.FAILED: frozenset({KBStatus.DRAFT}),  # допускается перезапуск
}


# Поля, защищённые от изменения после перехода в ACTIVE.
_IMMUTABLE_AFTER_ACTIVE: frozenset[str] = frozenset(
    {
        "knowledge_base_version",
        "setup_job_id",
        "rag_card_count",
        "chunk_count",
        "index_version",
        "retrieval_test_report_id",
        "published_by",
        "published_at",
    }
)


class InvalidKBTransitionError(ValueError):
    def __init__(self, from_status: KBStatus, to_status: KBStatus) -> None:
        super().__init__(f"Invalid KB status transition: {from_status.value} → {to_status.value}")


class ImmutableKBFieldError(ValueError):
    def __init__(self, field: str) -> None:
        super().__init__(f"Field {field!r} is immutable after KB transitioned to ACTIVE")


class KnowledgeBaseVersion(BaseModel):
    """Версия Knowledge Base. ACTIVE-версия иммутабельна (INV-KB-002)."""

    # validate_assignment отключён сознательно: transition_to() — единственный путь
    # смены статуса. validate_assignment ломал бы промежуточное состояние при
    # одновременной смене status и is_active.
    model_config = ConfigDict(extra="forbid")

    knowledge_base_version: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    status: KBStatus = KBStatus.DRAFT
    rag_card_count: int = Field(0, ge=0)
    chunk_count: int = Field(0, ge=0)
    index_version: str | None = None
    retrieval_test_report_id: str | None = None
    published_by: str | None = None
    published_at: datetime | None = None
    is_active: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _is_active_consistent(self) -> KnowledgeBaseVersion:
        if self.is_active and self.status != KBStatus.ACTIVE:
            raise ValueError("is_active=True requires status=ACTIVE")
        if self.status == KBStatus.ACTIVE and not self.is_active:
            raise ValueError("status=ACTIVE requires is_active=True")
        return self

    def can_transition_to(self, new_status: KBStatus) -> bool:
        return new_status in _KB_TRANSITIONS.get(self.status, frozenset())

    def transition_to(self, new_status: KBStatus) -> None:
        if not self.can_transition_to(new_status):
            raise InvalidKBTransitionError(self.status, new_status)
        if new_status == KBStatus.ACTIVE:
            # При активации требуем published_at и index_version.
            if self.index_version is None:
                raise ValueError("Cannot activate KB without index_version")
            self.is_active = True
        elif new_status == KBStatus.DEPRECATED and self.is_active:
            # Деактивация: снимаем is_active атомарно вместе со сменой статуса.
            self.is_active = False
        self.status = new_status
