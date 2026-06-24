"""ChunkManifestDTO (SETUP-08 / T-S08-001).

Persisted результат batch chunking. Manifest хранит все chunks setup_job +
агрегированные счётчики by_type.

Source of truth — docs/02-system/features/SETUP-08-chunking.md §11.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.rag.chunk import Chunk


class ChunkManifestDTO(BaseModel):
    """Иммутабельный manifest chunks per setup_job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_id: str = Field(..., min_length=1, max_length=128)
    setup_job_id: str = Field(..., min_length=1)
    chunks: list[Chunk] = Field(default_factory=list)
    total_chunks: int = Field(default=0, ge=0)
    by_type: dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    created_by: str = Field(..., min_length=1, max_length=128)


class ChunkingRunDTO(BaseModel):
    """Агрегат run-а chunking."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunking_run_id: str = Field(..., min_length=1, max_length=128)
    setup_job_id: str = Field(..., min_length=1)
    manifest_id: str = Field(..., min_length=1)
    triggered_by: str = Field(..., min_length=1)
    total_cards: int = Field(default=0, ge=0)
    chunks_created: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    started_at: datetime
    finished_at: datetime
