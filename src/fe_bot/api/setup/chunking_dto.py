"""SETUP-08 chunking API DTOs (T-S08-012)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunChunkingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChunkItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    doc_id: str
    chunk_type: str
    section_title: str | None = None
    chunk_text: str
    embedding_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    priority: int
    source_section_id: str | None = None
    token_count: int | None = None
    created_at: datetime
    status: str


class ChunkManifestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_id: str
    setup_job_id: str
    total_chunks: int
    by_type: dict[str, int]
    chunks: list[ChunkItemDTO]
    created_at: datetime
    created_by: str


class ChunkPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    chunks: list[ChunkItemDTO]


class ChunkingRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunking_run_id: str
    setup_job_id: str
    manifest_id: str
    triggered_by: str
    total_cards: int
    chunks_created: int
    duration_ms: int
    started_at: datetime
    finished_at: datetime
