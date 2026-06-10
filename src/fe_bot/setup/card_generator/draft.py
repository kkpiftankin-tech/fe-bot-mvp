"""LLM draft schema для RAG Card Generator.

LLM возвращает draft в этом формате; генератор собирает из него
полный RAGCard + RAGMetadata.

Separate-schema подход (не возвращать RAGCard напрямую) — потому что:
- LLM не должна назначать doc_id / created_at / created_by;
- LLM выбирает doc_type из подмножества;
- Поля confidence_level и confidence идут вместе.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from schemas.rag.ontology import (
    ConfidenceLevel,
    DataSource,
    DocType,
    Domain,
    Phase,
    TaskType,
)


class RAGCardDraft(BaseModel):
    """Структурированный output LLM для одной карточки."""

    model_config = ConfigDict(extra="forbid")

    doc_type: DocType
    title: str = Field(..., min_length=1, max_length=512)
    summary: str = Field(..., min_length=1, max_length=2000)
    body_markdown: str = Field(..., min_length=1)
    domain: list[Domain] = Field(default_factory=list)
    task_type: list[TaskType] = Field(default_factory=list)
    data_source: list[DataSource] = Field(default_factory=list)
    entity_type: list[str] = Field(default_factory=list)
    phase: list[Phase] = Field(..., min_length=1)
    agent_targets: list[str] = Field(default_factory=list)
    required_input_fields: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    retrieval_tags: list[str] = Field(..., min_length=1)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    confidence: float = Field(..., ge=0.0, le=1.0)
