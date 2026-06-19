"""RAGCardSourceLinkDTO (SETUP-05) — lineage relation RAG-карточка ↔ parsed_section.

Расширяет SETUP-03 source lineage до уровня RAG-карточек: запись также попадает
в ``SourceLineageRelation`` через ``SourceLifecycleService.link_artifact()``.

``LineageRelationType.GENERATED_FROM`` и ``LineageTargetType.RAG_CARD`` уже
существуют в schemas/setup/lineage.py.

Source of truth — docs/03-architecture/services/data-transfer-objects.md DTO-63.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.setup.lineage import LineageRelationType


class RAGCardSourceLinkDTO(BaseModel):
    """Связь RAG-карточки с parsed_section/source_document.

    Идемпотентен по ``(doc_id, card_version, source_section_id, relation_type)``.

    Storage: PostgreSQL `rag_card_source_links` (план); MVP — in-memory.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_link_id: str = Field(..., min_length=1)
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    source_document_id: str = Field(..., min_length=1)
    source_section_id: str = Field(..., min_length=1)
    relation_type: LineageRelationType = LineageRelationType.GENERATED_FROM
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
