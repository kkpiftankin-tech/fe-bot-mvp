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
    """Жизненный цикл карточки (см. docs/06-rag/card-lifecycle.md, rag-lifecycle.md)."""

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
    # SETUP-05 lifecycle statuses (см. docs/06-rag/card-lifecycle.md).
    GENERATION_FAILED = "generation_failed"
    METADATA_INCOMPLETE = "metadata_incomplete"
    BODY_EMPTY = "body_empty"
    LOW_CONFIDENCE = "low_confidence"
    READY_FOR_METADATA_VALIDATION = "ready_for_metadata_validation"
    REJECTED = "rejected"


_FORWARD_CARD_TRANSITIONS: dict[CardStatus, frozenset[CardStatus]] = {
    CardStatus.DRAFT: frozenset(
        {
            CardStatus.GENERATED,
            # SETUP-05 precheck outcomes:
            CardStatus.GENERATION_FAILED,
            CardStatus.METADATA_INCOMPLETE,
            CardStatus.BODY_EMPTY,
            CardStatus.LOW_CONFIDENCE,
            CardStatus.DEPRECATED,
        }
    ),
    CardStatus.GENERATED: frozenset(
        {
            CardStatus.METADATA_VALIDATED,
            CardStatus.REVIEW_REQUIRED,
            # SETUP-05: переход в ready_for_metadata_validation для SETUP-07.
            CardStatus.READY_FOR_METADATA_VALIDATION,
            CardStatus.DEPRECATED,
        }
    ),
    CardStatus.METADATA_VALIDATED: frozenset(
        {CardStatus.REVIEW_REQUIRED, CardStatus.APPROVED, CardStatus.DEPRECATED}
    ),
    CardStatus.READY_FOR_METADATA_VALIDATION: frozenset(
        {
            CardStatus.METADATA_VALIDATED,
            CardStatus.REVIEW_REQUIRED,  # SETUP-07 failure → review
            CardStatus.DEPRECATED,
        }
    ),
    CardStatus.REVIEW_REQUIRED: frozenset(
        {
            CardStatus.APPROVED,
            CardStatus.READY_FOR_METADATA_VALIDATION,  # SETUP-06 approval → S07
            CardStatus.REJECTED,
            CardStatus.DRAFT,  # legacy regenerate path
            CardStatus.DEPRECATED,
        }
    ),
    CardStatus.LOW_CONFIDENCE: frozenset({CardStatus.REVIEW_REQUIRED, CardStatus.DEPRECATED}),
    CardStatus.METADATA_INCOMPLETE: frozenset({CardStatus.REVIEW_REQUIRED, CardStatus.DEPRECATED}),
    CardStatus.BODY_EMPTY: frozenset({CardStatus.GENERATION_FAILED, CardStatus.DEPRECATED}),
    CardStatus.GENERATION_FAILED: frozenset({CardStatus.DRAFT, CardStatus.DEPRECATED}),
    CardStatus.APPROVED: frozenset(
        {CardStatus.CHUNKED, CardStatus.REVIEW_REQUIRED, CardStatus.DEPRECATED}
    ),
    CardStatus.CHUNKED: frozenset({CardStatus.EMBEDDED, CardStatus.DEPRECATED}),
    CardStatus.EMBEDDED: frozenset({CardStatus.INDEXED, CardStatus.DEPRECATED}),
    CardStatus.INDEXED: frozenset({CardStatus.PUBLISHED, CardStatus.DEPRECATED}),
    CardStatus.PUBLISHED: frozenset({CardStatus.DEPRECATED}),
    CardStatus.REJECTED: frozenset(),  # terminal
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
    """RAG-карточка — основная единица знания до chunking.

    SETUP-05 extension: добавлены optional поля для versioning, attachment
    к Markdown artifact и primary section reference. Все новые поля имеют
    defaults для backward-compat с SETUP-01..03 legacy pipeline.
    """

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

    # --- SETUP-05 extension fields (all optional, backward-compat) ---
    setup_job_id: str | None = Field(
        default=None,
        description="RAGSetupJob ID. Optional для legacy совместимости.",
    )
    card_version: str = Field(
        default="1.0",
        pattern=r"^\d+(\.\d+){0,2}$",
        description="Версия карточки (monotonic при regenerate).",
    )
    markdown_artifact_id: str | None = Field(
        default=None,
        description="Ссылка на RAGCardMarkdownDTO artifact в Object Storage.",
    )
    primary_source_section_id: str | None = Field(
        default=None,
        description="Главная ParsedSection.section_id для этой карточки.",
    )
    created_by_type: str | None = Field(
        default=None,
        description="service|user|system",
    )
    created_by_id: str | None = Field(
        default=None,
        description="Дублирует created_by для типизированного фильтра.",
    )
    review_required_reason: str | None = Field(
        default=None,
        max_length=2000,
        description="Читаемое объяснение, почему карточка попала в review_required.",
    )
    error_code: str | None = Field(
        default=None,
        description="RAGCardGenerationErrorCode при status=generation_failed.",
    )
    error_message: str | None = Field(
        default=None,
        max_length=4000,
    )

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
