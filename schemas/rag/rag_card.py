"""RAGCardDTO (DTO-11) — RAG-карточка с YAML front matter + Markdown body.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-11,
docs/06-rag/rag-lifecycle.md (статусы).
"""

from __future__ import annotations

import io
from datetime import datetime
from enum import StrEnum

import yaml
from pydantic import BaseModel, ConfigDict, Field

from schemas.rag.ontology import DocType


class CardStatus(StrEnum):
    """Жизненный цикл карточки (см. docs/06-rag/rag-lifecycle.md)."""

    DRAFT = "draft"
    GENERATED = "generated"
    METADATA_VALIDATED = "metadata_validated"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


_FORWARD_CARD_TRANSITIONS: dict[CardStatus, frozenset[CardStatus]] = {
    CardStatus.DRAFT: frozenset({CardStatus.GENERATED, CardStatus.DEPRECATED}),
    CardStatus.GENERATED: frozenset(
        {CardStatus.METADATA_VALIDATED, CardStatus.REVIEW_REQUIRED, CardStatus.DEPRECATED}
    ),
    CardStatus.METADATA_VALIDATED: frozenset(
        {CardStatus.REVIEW_REQUIRED, CardStatus.APPROVED, CardStatus.DEPRECATED}
    ),
    CardStatus.REVIEW_REQUIRED: frozenset(
        {
            CardStatus.APPROVED,
            CardStatus.DRAFT,  # rejected → back to draft for regeneration
            CardStatus.DEPRECATED,
        }
    ),
    CardStatus.APPROVED: frozenset(
        {CardStatus.CHUNKED, CardStatus.REVIEW_REQUIRED, CardStatus.DEPRECATED}
    ),
    CardStatus.CHUNKED: frozenset({CardStatus.EMBEDDED, CardStatus.DEPRECATED}),
    CardStatus.EMBEDDED: frozenset({CardStatus.INDEXED, CardStatus.DEPRECATED}),
    CardStatus.INDEXED: frozenset({CardStatus.PUBLISHED, CardStatus.DEPRECATED}),
    CardStatus.PUBLISHED: frozenset({CardStatus.DEPRECATED}),
    CardStatus.DEPRECATED: frozenset(),  # terminal
}


class InvalidCardTransitionError(ValueError):
    def __init__(self, from_status: CardStatus, to_status: CardStatus) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid RAG card status transition: {from_status.value} → {to_status.value}"
        )


class RAGCard(BaseModel):
    """RAG-карточка — основная единица знания до chunking."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    doc_id: str = Field(..., min_length=1)
    doc_type: DocType
    title: str = Field(..., min_length=1, max_length=512)
    version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    status: CardStatus = CardStatus.DRAFT
    front_matter: dict[str, object] = Field(default_factory=dict)
    body_markdown: str = Field(..., min_length=1)
    source_document_ids: list[str] = Field(default_factory=list)
    source_section_ids: list[str] = Field(default_factory=list)
    confidence_level: str | None = None
    created_by: str
    reviewed_by: str | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    def can_transition_to(self, new_status: CardStatus) -> bool:
        return new_status in _FORWARD_CARD_TRANSITIONS.get(self.status, frozenset())

    def transition_to(self, new_status: CardStatus) -> None:
        if not self.can_transition_to(new_status):
            raise InvalidCardTransitionError(self.status, new_status)
        self.status = new_status

    def to_markdown(self) -> str:
        """Сериализует карточку в Markdown с YAML front matter."""
        buf = io.StringIO()
        buf.write("---\n")
        yaml.safe_dump(
            self.front_matter, buf, sort_keys=True, allow_unicode=True, default_flow_style=False
        )
        buf.write("---\n\n")
        buf.write(self.body_markdown)
        return buf.getvalue()

    @classmethod
    def parse_front_matter(cls, markdown_text: str) -> tuple[dict[str, object], str]:
        """Парсит Markdown-документ с YAML front matter.

        Returns:
            (front_matter_dict, body_markdown_without_frontmatter)
        """
        if not markdown_text.startswith("---\n"):
            return {}, markdown_text
        try:
            _, fm, body = markdown_text.split("---\n", 2)
        except ValueError as exc:
            raise ValueError("Malformed YAML front matter delimiter") from exc
        data = yaml.safe_load(fm) or {}
        if not isinstance(data, dict):
            raise ValueError("YAML front matter must be a mapping")
        return data, body.lstrip("\n")
