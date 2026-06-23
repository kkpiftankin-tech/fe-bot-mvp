"""RAGCardEditLockDTO (SETUP-06 / T-S06-005).

Lock на редактирование карточки. TTL-based с автоматическим освобождением.
В MVP — in-memory (Redis в плане).

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §11.2.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EditLockStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"


class RAGCardEditLockDTO(BaseModel):
    """Lock на редактирование RAG-карточки.

    Один active lock per doc_id. ``expires_at`` определяет TTL.

    Storage: Redis `rag_card_edit_lock:{doc_id}` (план); MVP — in-memory.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lock_id: str = Field(..., min_length=1, max_length=128)
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+\.\d+$")
    locked_by: str = Field(..., min_length=1, max_length=128)
    locked_at: datetime
    expires_at: datetime
    status: EditLockStatus = EditLockStatus.ACTIVE

    def is_expired(self, now: datetime) -> bool:
        """Returns True если lock TTL истёк (даже если status=ACTIVE)."""
        return self.expires_at <= now
