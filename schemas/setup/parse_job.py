"""ParseJob DTO (SETUP-04) — lifecycle-сущность задания парсинга документов.

ParseJob — отдельная lifecycle entity, независимая от RAGSetupJob.
Один RAGSetupJob может породить несколько ParseJob (retry, incremental parse).

Source of truth — SETUP-04 spec §15.1.
Storage — PostgreSQL (таблица parse_jobs). MVP: in-memory dict в ParseService.
Producer — SVC-07 Document Parser Service.
Consumers — SVC-04 Setup Orchestrator, SVC-01 Frontend UI, SVC-36 Audit Service.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ParseJobStatus(StrEnum):
    """Статусы lifecycle ParseJob.

    Допустимые переходы объявлены в PARSE_JOB_ALLOWED_TRANSITIONS ниже.
    """

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParseErrorCode(StrEnum):
    """Коды ошибок парсинга.

    Используются в ParseJob.error_code, ParseJobDocument.error_code и ParseError.
    HTTP-маппинг см. в функции http_status_for().
    """

    UNSUPPORTED_PARSE_FORMAT = "UNSUPPORTED_PARSE_FORMAT"
    RAW_FILE_NOT_FOUND = "RAW_FILE_NOT_FOUND"
    TEXT_EXTRACTION_FAILED = "TEXT_EXTRACTION_FAILED"
    PDF_TEXT_LAYER_NOT_FOUND = "PDF_TEXT_LAYER_NOT_FOUND"
    DOCX_EXTRACTION_FAILED = "DOCX_EXTRACTION_FAILED"
    TABLE_EXTRACTION_FAILED = "TABLE_EXTRACTION_FAILED"
    JSON_PARSE_FAILED = "JSON_PARSE_FAILED"
    SECTION_DETECTION_FAILED = "SECTION_DETECTION_FAILED"
    SECTION_SAVE_FAILED = "SECTION_SAVE_FAILED"
    PARSE_TIMEOUT = "PARSE_TIMEOUT"
    NO_PARSEABLE_DOCUMENTS = "NO_PARSEABLE_DOCUMENTS"
    DOCUMENT_NOT_PARSEABLE_STATUS = "DOCUMENT_NOT_PARSEABLE_STATUS"
    PARSE_JOB_ALREADY_RUNNING = "PARSE_JOB_ALREADY_RUNNING"
    CLASSIFICATION_FAILED = "CLASSIFICATION_FAILED"


class ParserStrategy(StrEnum):
    """Стратегия парсинга документа (выбирается rule-based classifier'ом).

    Соответствует реальным библиотекам: pypdf, python-docx, openpyxl, csv, json.
    OCR исключён из scope.
    """

    MARKDOWN = "markdown"
    TEXT = "text"
    PDF_TEXT = "pdf_text"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    JSON = "json"


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

#: Явный граф допустимых переходов ParseJobStatus.
#: Ключ — текущий статус. Значение — множество разрешённых целевых статусов.
PARSE_JOB_ALLOWED_TRANSITIONS: dict[ParseJobStatus, frozenset[ParseJobStatus]] = {
    ParseJobStatus.CREATED: frozenset(
        {
            ParseJobStatus.QUEUED,
            ParseJobStatus.CANCELLED,
        }
    ),
    ParseJobStatus.QUEUED: frozenset(
        {
            ParseJobStatus.RUNNING,
            ParseJobStatus.CANCELLED,
            ParseJobStatus.FAILED,  # сервис упал до начала обработки
        }
    ),
    ParseJobStatus.RUNNING: frozenset(
        {
            ParseJobStatus.COMPLETED,
            ParseJobStatus.PARTIAL_SUCCESS,
            ParseJobStatus.FAILED,
            ParseJobStatus.CANCELLED,
        }
    ),
    # partial_success допускает повтор (retry creates a new ParseJob).
    ParseJobStatus.PARTIAL_SUCCESS: frozenset(),  # terminal
    ParseJobStatus.COMPLETED: frozenset(),  # terminal
    ParseJobStatus.FAILED: frozenset(),  # terminal; retry → новый ParseJob
    ParseJobStatus.CANCELLED: frozenset(),  # terminal
}


class InvalidParseJobTransitionError(ValueError):
    """Попытка перехода ParseJob в недопустимый статус."""

    def __init__(
        self,
        parse_job_id: str,
        from_status: ParseJobStatus,
        to_status: ParseJobStatus,
    ) -> None:
        self.parse_job_id = parse_job_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid ParseJob status transition for {parse_job_id}: "
            f"{from_status.value} → {to_status.value}"
        )


# ---------------------------------------------------------------------------
# HTTP status mapping
# ---------------------------------------------------------------------------


def http_status_for(code: ParseErrorCode) -> int:
    """Возвращает HTTP-статус для ParseErrorCode.

    Используется API-слоем при формировании ответов на ошибочные запросы.
    Семантика:
      400 — клиентская ошибка (неверный формат, дублирующий запрос).
      404 — ресурс не найден.
      409 — конфликт состояния.
      422 — файл пришёл, но не может быть обработан.
      500 — внутренняя ошибка сервиса.
      504 — таймаут.
    """
    _MAP: dict[ParseErrorCode, int] = {
        ParseErrorCode.UNSUPPORTED_PARSE_FORMAT: 400,
        ParseErrorCode.RAW_FILE_NOT_FOUND: 404,
        ParseErrorCode.TEXT_EXTRACTION_FAILED: 422,
        ParseErrorCode.PDF_TEXT_LAYER_NOT_FOUND: 422,
        ParseErrorCode.DOCX_EXTRACTION_FAILED: 422,
        ParseErrorCode.TABLE_EXTRACTION_FAILED: 422,
        ParseErrorCode.JSON_PARSE_FAILED: 422,
        ParseErrorCode.SECTION_DETECTION_FAILED: 422,
        ParseErrorCode.SECTION_SAVE_FAILED: 500,
        ParseErrorCode.PARSE_TIMEOUT: 504,
        ParseErrorCode.NO_PARSEABLE_DOCUMENTS: 400,
        ParseErrorCode.DOCUMENT_NOT_PARSEABLE_STATUS: 409,
        ParseErrorCode.PARSE_JOB_ALREADY_RUNNING: 409,
        ParseErrorCode.CLASSIFICATION_FAILED: 500,
    }
    return _MAP[code]


# ---------------------------------------------------------------------------
# ParseJob model
# ---------------------------------------------------------------------------


class ParseJob(BaseModel):
    """Задание парсинга документов (SETUP-04, DTO-54).

    Самостоятельная lifecycle-entity: один RAGSetupJob → 1..N ParseJob
    (повторный запуск создаёт новый ParseJob, а не переиспользует старый).

    Storage: PostgreSQL, таблица parse_jobs.
    MVP: in-memory dict в ParseService (SVC-07).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    parse_job_id: str = Field(..., min_length=1, description="UUID задания парсинга.")
    setup_job_id: str = Field(..., min_length=1, description="Ссылка на родительский RAGSetupJob.")
    requested_by: str = Field(..., min_length=1, description="user_id инициатора запроса.")
    status: ParseJobStatus = Field(
        ParseJobStatus.CREATED,
        description="Текущий статус. Переходы валидируются через transition_to().",
    )

    # --- progress counters ---
    total_documents: int = Field(
        0, ge=0, description="Количество документов, поставленных в очередь на парсинг."
    )
    processed_documents: int = Field(0, ge=0, description="Документов успешно обработано.")
    failed_documents: int = Field(0, ge=0, description="Документов завершилось ошибкой.")
    total_sections: int = Field(0, ge=0, description="Итоговое число извлечённых секций.")
    low_confidence_sections: int = Field(
        0, ge=0, description="Секций с confidence < порога (требуют ревью)."
    )

    # --- timing ---
    started_at: datetime | None = Field(None, description="Время перехода в RUNNING.")
    finished_at: datetime | None = Field(None, description="Время перехода в terminal-статус.")
    created_at: datetime = Field(..., description="Время создания записи (UTC).")
    updated_at: datetime = Field(..., description="Время последнего обновления (UTC).")

    # --- config / error ---
    config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Конфигурация задания: timeout_sec, max_section_size, confidence_threshold и др."
        ),
    )
    error_code: ParseErrorCode | None = Field(None, description="Код ошибки при status=failed.")
    error_message: str | None = Field(
        None, max_length=4000, description="Человекочитаемое описание ошибки."
    )

    # --- business invariants ---

    @model_validator(mode="after")
    def _counters_consistent(self) -> ParseJob:
        """processed + failed не превышает total."""
        if self.processed_documents + self.failed_documents > self.total_documents:
            raise ValueError("processed_documents + failed_documents cannot exceed total_documents")
        return self

    # --- state machine ---

    def can_transition_to(self, new_status: ParseJobStatus) -> bool:
        """True если переход из текущего статуса в new_status допустим."""
        return new_status in PARSE_JOB_ALLOWED_TRANSITIONS.get(self.status, frozenset())

    def transition_to(self, new_status: ParseJobStatus) -> None:
        """Выполняет переход статуса с валидацией.

        Raises:
            InvalidParseJobTransitionError: если переход запрещён.
        """
        if not self.can_transition_to(new_status):
            raise InvalidParseJobTransitionError(self.parse_job_id, self.status, new_status)
        self.status = new_status

    @property
    def is_terminal(self) -> bool:
        """True если задание в terminal-статусе (нельзя перейти дальше)."""
        return not PARSE_JOB_ALLOWED_TRANSITIONS.get(self.status, frozenset())
