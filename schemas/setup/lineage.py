"""SourceDocumentLineage DTO (SETUP-03 / T-S03-004).

Граф связей source document → derived artifacts (parsed sections, RAG cards,
chunks, KB versions). Уникальность по (source_id, target_type, target_id,
relation_type) — повторный link не создаёт дубликат.

Source of truth — SETUP-03 spec §15.2 (SourceLineageDTO) + §16.2 LineageUpdatedDTO.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LineageTargetType(StrEnum):
    """Тип downstream-артефакта, на который ссылается lineage relation."""

    PARSED_SECTION = "parsed_section"  # из SETUP-04
    RAG_CARD = "rag_card"  # из SETUP-05
    CHUNK = "chunk"  # из SETUP-08
    EMBEDDING = "embedding"  # из SETUP-09
    PROCESSING_REPORT = "processing_report"
    KNOWLEDGE_BASE_VERSION = "knowledge_base_version"  # из SETUP-11


class LineageRelationType(StrEnum):
    """Семантика связи."""

    PARSED_FROM = "parsed_from"  # section / chunk сделан парсингом source
    GENERATED_FROM = "generated_from"  # card сгенерирован из section'ов source
    DERIVED_FROM = "derived_from"  # general derivation (embeddings, etc.)
    INCLUDED_IN = "included_in"  # source включён в KB version
    REFERENCED_BY = "referenced_by"  # source упомянут в derived artifact


class SourceLineageRelation(BaseModel):
    """Единичная lineage relation.

    Уникальный ключ: (source_document_id, target_type, target_id, relation_type).
    Неизменяема после создания.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lineage_id: str = Field(..., min_length=1)
    source_document_id: str = Field(..., min_length=1)
    target_type: LineageTargetType
    target_id: str = Field(..., min_length=1, max_length=255)
    relation_type: LineageRelationType
    created_by_service: str = Field(..., min_length=1, max_length=255)
    event_id: str = Field(..., min_length=1, max_length=128)
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageCounters(BaseModel):
    """Агрегированные счётчики derived artifacts по source document."""

    model_config = ConfigDict(extra="forbid")

    parsed_sections_count: int = Field(default=0, ge=0)
    rag_cards_count: int = Field(default=0, ge=0)
    chunks_count: int = Field(default=0, ge=0)
    embeddings_count: int = Field(default=0, ge=0)
    processing_reports_count: int = Field(default=0, ge=0)
    knowledge_base_versions_count: int = Field(default=0, ge=0)


class SourceLineageDTO(BaseModel):
    """Ответ GET /sources/{id}/lineage."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    relations: list[SourceLineageRelation] = Field(default_factory=list)
    counters: LineageCounters = Field(default_factory=LineageCounters)
