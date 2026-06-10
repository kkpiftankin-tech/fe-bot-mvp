"""VectorIndexDTO (DTO-16) — версия векторного индекса.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-16.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VectorIndexStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class VectorIndex(BaseModel):
    """Версия векторного индекса Knowledge Base."""

    model_config = ConfigDict(extra="forbid")

    index_version: str = Field(..., min_length=1)
    knowledge_base_version: str | None = None
    collection_names: list[str] = Field(default_factory=list)
    embedding_model: str = Field(..., min_length=1)
    chunks_count: int = Field(0, ge=0)
    indexed_chunks_count: int = Field(0, ge=0)
    failed_chunks_count: int = Field(0, ge=0)
    status: VectorIndexStatus = VectorIndexStatus.BUILDING
    created_at: datetime
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _counts_consistent(self) -> VectorIndex:
        if self.indexed_chunks_count + self.failed_chunks_count > self.chunks_count:
            raise ValueError(
                "indexed_chunks_count + failed_chunks_count cannot exceed chunks_count"
            )
        if self.status == VectorIndexStatus.READY and self.published_at is None:
            # READY-индекс может ещё не быть привязан к KB-version, это ок.
            pass
        return self
