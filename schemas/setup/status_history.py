"""SourceDocumentStatusHistory DTO (SETUP-03 / T-S03-002).

Хронология изменений статуса source document. Каждая запись неизменяема
после создания. event_id обеспечивает идемпотентность при retry'ях
от downstream-сервисов.

Source of truth — SETUP-03 spec §15.2 (SourceStatusHistoryDTO) + §12 (state
machine rules).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.setup.source_document import SourceDocumentStatus


class ChangedByType(StrEnum):
    """Кто инициировал смену статуса (§12 спека)."""

    SERVICE = "service"  # downstream-сервис (parser, generator, etc.)
    USER = "user"  # пользовательское действие через UI/API
    SYSTEM = "system"  # автоматический trigger (cron, recovery, etc.)


class SourceStatusHistoryEntry(BaseModel):
    """Единичная запись истории смены статуса.

    Неизменяема после создания. Идемпотентность через event_id —
    повторная запись с тем же event_id игнорируется.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status_history_id: str = Field(..., min_length=1)
    source_document_id: str = Field(..., min_length=1)
    old_status: SourceDocumentStatus | None = None
    new_status: SourceDocumentStatus
    reason: str | None = Field(default=None, max_length=2000)
    event_id: str = Field(..., min_length=1, max_length=128)
    changed_by_type: ChangedByType = ChangedByType.SERVICE
    changed_by_id: str = Field(..., min_length=1, max_length=255)
    changed_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceStatusHistoryDTO(BaseModel):
    """Ответ GET /sources/{id}/status-history."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    items: list[SourceStatusHistoryEntry] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


# ============================================================
# State machine — допустимые переходы между статусами.
# §12 спека: бизнес-правила перехода.
# ============================================================

_LIFECYCLE = SourceDocumentStatus

# from -> set of allowed `to`
ALLOWED_TRANSITIONS: dict[SourceDocumentStatus, set[SourceDocumentStatus]] = {
    # Initial: только что загружен → можно зарегистрировать или забраковать.
    _LIFECYCLE.UPLOADED: {
        _LIFECYCLE.REGISTERED,
        _LIFECYCLE.FAILED_VALIDATION,
        _LIFECYCLE.REMOVED,
    },
    # Зарегистрирован → metadata extraction или прямо parsing.
    _LIFECYCLE.REGISTERED: {
        _LIFECYCLE.METADATA_EXTRACTED,
        _LIFECYCLE.WAITING_FOR_PARSING,
        _LIFECYCLE.PARSING,
        _LIFECYCLE.REMOVED,
        _LIFECYCLE.PROCESSING_FAILED,
    },
    _LIFECYCLE.METADATA_EXTRACTED: {
        _LIFECYCLE.WAITING_FOR_PARSING,
        _LIFECYCLE.PARSING,
        _LIFECYCLE.REVIEW_REQUIRED,
        _LIFECYCLE.PROCESSING_FAILED,
        _LIFECYCLE.REMOVED,
    },
    _LIFECYCLE.WAITING_FOR_PARSING: {
        _LIFECYCLE.PARSING,
        _LIFECYCLE.REMOVED,
        _LIFECYCLE.PROCESSING_FAILED,
    },
    # Парсинг → успех или ошибка.
    _LIFECYCLE.PARSING: {
        _LIFECYCLE.PARSED,
        _LIFECYCLE.SECTIONS_EXTRACTED,
        _LIFECYCLE.PARSE_FAILED,
        _LIFECYCLE.PROCESSING_FAILED,
    },
    _LIFECYCLE.PARSED: {
        _LIFECYCLE.SECTIONS_EXTRACTED,
        _LIFECYCLE.RAG_CARDS_GENERATING,
        _LIFECYCLE.REVIEW_REQUIRED,
        _LIFECYCLE.PROCESSING_FAILED,
        _LIFECYCLE.ARCHIVED,
        _LIFECYCLE.REMOVED,
    },
    _LIFECYCLE.SECTIONS_EXTRACTED: {
        _LIFECYCLE.RAG_CARDS_GENERATING,
        _LIFECYCLE.REVIEW_REQUIRED,
        _LIFECYCLE.PROCESSING_FAILED,
    },
    _LIFECYCLE.RAG_CARDS_GENERATING: {
        _LIFECYCLE.RAG_CARDS_GENERATED,
        _LIFECYCLE.PROCESSING_FAILED,
        _LIFECYCLE.REVIEW_REQUIRED,
    },
    _LIFECYCLE.RAG_CARDS_GENERATED: {
        _LIFECYCLE.READY_FOR_INDEXING,
        _LIFECYCLE.REVIEW_REQUIRED,
        _LIFECYCLE.PROCESSING_FAILED,
    },
    _LIFECYCLE.REVIEW_REQUIRED: {
        _LIFECYCLE.READY_FOR_INDEXING,
        _LIFECYCLE.PROCESSING_FAILED,
        _LIFECYCLE.ARCHIVED,
    },
    _LIFECYCLE.READY_FOR_INDEXING: {
        _LIFECYCLE.PUBLISHED,
        _LIFECYCLE.PROCESSING_FAILED,
    },
    _LIFECYCLE.PUBLISHED: {
        _LIFECYCLE.DEPRECATED,
        _LIFECYCLE.ARCHIVED,
    },
    # Восстановление после ошибок (retry endpoint, T-S03-021).
    _LIFECYCLE.PARSE_FAILED: {
        _LIFECYCLE.WAITING_FOR_PARSING,
        _LIFECYCLE.PARSING,
        _LIFECYCLE.ARCHIVED,
        _LIFECYCLE.REMOVED,
    },
    _LIFECYCLE.PROCESSING_FAILED: {
        _LIFECYCLE.WAITING_FOR_PARSING,
        _LIFECYCLE.PARSING,
        _LIFECYCLE.METADATA_EXTRACTED,
        _LIFECYCLE.ARCHIVED,
        _LIFECYCLE.REMOVED,
    },
    # Terminal: только в DEPRECATED или назад в archived (admin).
    _LIFECYCLE.ARCHIVED: {
        _LIFECYCLE.DEPRECATED,
        _LIFECYCLE.REMOVED,
    },
    _LIFECYCLE.DEPRECATED: set(),  # terminal
    # REMOVED — terminal. Восстановление не поддерживается в MVP.
    _LIFECYCLE.REMOVED: set(),
    _LIFECYCLE.FAILED_VALIDATION: {
        _LIFECYCLE.REMOVED,
    },
    # Legacy:
    _LIFECYCLE.FAILED: {
        _LIFECYCLE.WAITING_FOR_PARSING,
        _LIFECYCLE.ARCHIVED,
        _LIFECYCLE.REMOVED,
    },
    _LIFECYCLE.CONVERTED: {
        _LIFECYCLE.PARSED,
        _LIFECYCLE.PARSING,
        _LIFECYCLE.PROCESSING_FAILED,
    },
}


class InvalidStatusTransitionError(ValueError):
    """Попытка перейти в недопустимый статус (§18 спека / AC).

    `error_code = "INVALID_STATUS_TRANSITION"`.
    """

    def __init__(
        self,
        *,
        source_document_id: str,
        old_status: SourceDocumentStatus | None,
        new_status: SourceDocumentStatus,
    ) -> None:
        self.source_document_id = source_document_id
        self.old_status = old_status
        self.new_status = new_status
        old_repr = old_status.value if old_status else "None"
        super().__init__(
            f"Invalid status transition for {source_document_id}: {old_repr} → {new_status.value}"
        )


def validate_transition(
    old_status: SourceDocumentStatus | None,
    new_status: SourceDocumentStatus,
) -> bool:
    """Проверка допустимости перехода (без raise).

    None в `old_status` — initial state (документ только что создан),
    разрешён переход в UPLOADED или REGISTERED.

    Same-status переход (idempotency) разрешён всегда.
    """
    if old_status is None:
        return new_status in {
            SourceDocumentStatus.UPLOADED,
            SourceDocumentStatus.REGISTERED,
        }
    if old_status == new_status:
        return True  # idempotent
    return new_status in ALLOWED_TRANSITIONS.get(old_status, set())


def ensure_valid_transition(
    *,
    source_document_id: str,
    old_status: SourceDocumentStatus | None,
    new_status: SourceDocumentStatus,
) -> None:
    """Валидация с raise InvalidStatusTransitionError."""
    if not validate_transition(old_status, new_status):
        raise InvalidStatusTransitionError(
            source_document_id=source_document_id,
            old_status=old_status,
            new_status=new_status,
        )


# Re-export для удобства Literal type hint'ов.
ChangedByTypeLiteral = Literal["service", "user", "system"]
