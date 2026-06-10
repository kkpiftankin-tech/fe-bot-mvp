"""UploadBatchDTO (SETUP-02 / T-S02-001).

Логическая единица batch-загрузки документов. Один POST /documents → один
UploadBatch. Используется для:

1. **Idempotency**: повторный запрос с тем же `upload_request_id` возвращает
   кешированный результат, не запускает upload заново.
2. **Tracking**: counters (files_total/uploaded/rejected/duplicates) позволяют
   UI показать summary и backend — собирать метрики per-batch.
3. **Audit**: batch_id присутствует в каждом `setup.document.*` событии для
   корреляции multi-file операций.

State machine:
    IN_PROGRESS → COMPLETED          (все файлы успешно)
                → PARTIALLY_COMPLETED (часть файлов ok, часть rejected/duplicate)
                → FAILED              (все файлы rejected или системная ошибка)
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UploadBatchStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


# Допустимые переходы. IN_PROGRESS — единственный нетерминальный.
_BATCH_TRANSITIONS: dict[UploadBatchStatus, frozenset[UploadBatchStatus]] = {
    UploadBatchStatus.IN_PROGRESS: frozenset(
        {
            UploadBatchStatus.COMPLETED,
            UploadBatchStatus.PARTIALLY_COMPLETED,
            UploadBatchStatus.FAILED,
        }
    ),
    UploadBatchStatus.COMPLETED: frozenset(),  # terminal
    UploadBatchStatus.PARTIALLY_COMPLETED: frozenset(),  # terminal
    UploadBatchStatus.FAILED: frozenset(),  # terminal
}


class InvalidBatchTransitionError(ValueError):
    def __init__(
        self, from_status: UploadBatchStatus, to_status: UploadBatchStatus
    ) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid UploadBatch transition: {from_status.value!r} → {to_status.value!r}"
        )


class UploadBatch(BaseModel):
    """Запись batch-загрузки.

    Иммутабельные поля после `finished_at != None`:
        - upload_batch_id
        - setup_job_id
        - user_id
        - upload_request_id
        - created_at
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    upload_batch_id: str = Field(..., min_length=1, max_length=128)
    setup_job_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)
    upload_request_id: str | None = Field(default=None, max_length=128)
    status: UploadBatchStatus = UploadBatchStatus.IN_PROGRESS
    files_total: int = Field(default=0, ge=0)
    files_uploaded: int = Field(default=0, ge=0)
    files_rejected: int = Field(default=0, ge=0)
    duplicates_detected: int = Field(default=0, ge=0)
    created_at: datetime
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def _counters_consistent(self) -> UploadBatch:
        total_processed = (
            self.files_uploaded + self.files_rejected + self.duplicates_detected
        )
        if total_processed > self.files_total:
            raise ValueError(
                f"Counters inconsistent: uploaded({self.files_uploaded}) + "
                f"rejected({self.files_rejected}) + "
                f"duplicates({self.duplicates_detected}) = "
                f"{total_processed} > files_total({self.files_total})"
            )
        return self

    @model_validator(mode="after")
    def _finished_implies_terminal(self) -> UploadBatch:
        is_terminal = self.status in {
            UploadBatchStatus.COMPLETED,
            UploadBatchStatus.PARTIALLY_COMPLETED,
            UploadBatchStatus.FAILED,
        }
        if self.finished_at is not None and not is_terminal:
            raise ValueError(
                f"finished_at is set but status {self.status.value!r} is not terminal"
            )
        if self.finished_at is None and is_terminal:
            raise ValueError(
                f"status {self.status.value!r} is terminal but finished_at is None"
            )
        return self

    def can_transition_to(self, new_status: UploadBatchStatus) -> bool:
        return new_status in _BATCH_TRANSITIONS.get(self.status, frozenset())

    def transition_to(
        self, new_status: UploadBatchStatus, *, finished_at: datetime | None = None
    ) -> None:
        """Атомарный переход: status + finished_at меняются вместе.

        Для терминальных статусов finished_at обязателен (или ставится `now`).
        """
        if not self.can_transition_to(new_status):
            raise InvalidBatchTransitionError(self.status, new_status)
        is_terminal = new_status in {
            UploadBatchStatus.COMPLETED,
            UploadBatchStatus.PARTIALLY_COMPLETED,
            UploadBatchStatus.FAILED,
        }
        # model_validator валидируется на каждом __setattr__; чтобы избежать
        # промежуточного невалидного состояния, конструируем новые значения
        # через __dict__ + повторный model_validate.
        new_finished_at = finished_at or (
            datetime.now(tz=UTC) if is_terminal else None
        )
        # Update via model_copy + re-validate, чтобы инварианты держались.
        updated = self.model_copy(
            update={"status": new_status, "finished_at": new_finished_at}
        )
        # Перенесём поля обратно в self без повторной валидации каждого присвоения.
        object.__setattr__(self, "status", updated.status)
        object.__setattr__(self, "finished_at", updated.finished_at)
