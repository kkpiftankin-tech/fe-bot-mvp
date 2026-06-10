"""ChunkDTO (DTO-14) — логический фрагмент RAG-карточки, индексируемый в Vector DB.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-14,
docs/06-rag/chunk-schema.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChunkType(StrEnum):
    """Закрытое множество типов chunk (см. chunk-schema.md)."""

    SUMMARY = "summary"
    DEFINITION = "definition"
    INPUTS = "inputs"
    OUTPUTS = "outputs"
    FORMULA = "formula"
    VALIDATION = "validation"
    EXAMPLES = "examples"
    AGENT_USAGE = "agent_usage"
    CONSTRAINTS = "constraints"
    METADATA_SUMMARY = "metadata_summary"


class ChunkStatus(StrEnum):
    CREATED = "created"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    FAILED = "failed"


class Chunk(BaseModel):
    """Chunk RAG-карточки."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    chunk_type: ChunkType
    section_title: str | None = None
    chunk_text: str = Field(..., min_length=1)
    embedding_text: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(50, ge=0, le=100)
    source_section_id: str | None = None
    token_count: int | None = Field(None, ge=0)
    created_at: datetime
    status: ChunkStatus = ChunkStatus.CREATED
