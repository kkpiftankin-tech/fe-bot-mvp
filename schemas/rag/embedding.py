"""EmbeddingDTO (DTO-15) — embedding-вектор для chunk.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-15.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EmbeddingStatus(StrEnum):
    CREATED = "created"
    INDEXED = "indexed"
    FAILED = "failed"


class Embedding(BaseModel):
    """Embedding chunk-а."""

    model_config = ConfigDict(extra="forbid")

    embedding_id: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    embedding_vector: list[float] = Field(..., min_length=1)
    embedding_model: str = Field(..., min_length=1)
    dimension: int = Field(..., gt=0)
    index_version: str | None = None
    created_at: datetime
    status: EmbeddingStatus = EmbeddingStatus.CREATED
    error_message: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def _vector_dimension_matches(self) -> Embedding:
        actual = len(self.embedding_vector)
        if actual != self.dimension:
            raise ValueError(
                f"embedding_vector length {actual} != dimension {self.dimension}"
            )
        return self
