"""RAGMetadataDTO (DTO-12) — унифицированная metadata RAG-карточек.

Source of truth — docs/06-rag/metadata-schema.md, docs/06-rag/ontology.md.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.rag.ontology import (
    KNOWN_AGENTS,
    ConfidenceLevel,
    DataSource,
    DocType,
    Domain,
    Phase,
    TaskType,
)


class RAGMetadata(BaseModel):
    """Metadata RAG-документа. Все списки могут быть пустыми (но не None)."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(..., min_length=1)
    doc_type: DocType
    domain: list[Domain] = Field(default_factory=list)
    task_type: list[TaskType] = Field(default_factory=list)
    data_source: list[DataSource] = Field(default_factory=list)
    entity_type: list[str] = Field(default_factory=list)
    phase: list[Phase] = Field(..., min_length=1)
    agent_targets: list[str] = Field(default_factory=list)
    required_input_fields: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    feature_tables: list[str] = Field(default_factory=list)
    retrieval_tags: list[str] = Field(..., min_length=1)
    validation_rules: list[str] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    owner: str | None = None
    last_verified_at: datetime | None = None

    @field_validator("agent_targets")
    @classmethod
    def _agents_are_known(cls, v: list[str]) -> list[str]:
        unknown = [a for a in v if a not in KNOWN_AGENTS]
        if unknown:
            raise ValueError(
                f"Unknown agent_targets: {unknown}. Must be one of AGENTS.md registry."
            )
        return v

    @field_validator("retrieval_tags")
    @classmethod
    def _retrieval_tags_nonempty_strings(cls, v: list[str]) -> list[str]:
        if any(not tag.strip() for tag in v):
            raise ValueError("retrieval_tags must not contain empty strings")
        return v
