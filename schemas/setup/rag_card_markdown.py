"""RAGCardMarkdownDTO (SETUP-05) — финальный Markdown-документ карточки.

YAML front matter + body. Сохраняется как artifact в Object Storage и
загружается в Chunking Service (SETUP-08).

Source of truth — docs/03-architecture/services/data-transfer-objects.md DTO-62.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

_FRONT_MATTER_DELIMITER = "---\n"


class MalformedFrontMatterError(ValueError):
    """Markdown не содержит корректного YAML front matter блока."""


class RAGCardMarkdownDTO(BaseModel):
    """Финальный Markdown карточки: front matter + body.

    Storage: Object Storage `rag/cards/{setup_job_id}/{doc_id}.md`.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    markdown: str = Field(..., min_length=1)
    front_matter_yaml: str = Field(..., min_length=1)
    body_markdown: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _markdown_consistent(self) -> RAGCardMarkdownDTO:
        """``markdown`` обязан начинаться с front matter и содержать body."""
        if not self.markdown.startswith(_FRONT_MATTER_DELIMITER):
            raise MalformedFrontMatterError(
                "markdown must start with '---\\n' front matter delimiter"
            )
        # Должно быть как минимум 3 части после split: префикс "", front, body.
        parts = self.markdown.split(_FRONT_MATTER_DELIMITER, 2)
        if len(parts) < 3:
            raise MalformedFrontMatterError(
                "markdown must contain closing '---\\n' front matter delimiter"
            )
        actual_front = parts[1]
        if actual_front.strip() != self.front_matter_yaml.strip():
            raise ValueError("front_matter_yaml does not match front matter in markdown")
        return self

    # ----- factories -----

    @classmethod
    def from_parts(
        cls,
        *,
        doc_id: str,
        card_version: str,
        front_matter_yaml: str,
        body_markdown: str,
    ) -> RAGCardMarkdownDTO:
        """Build DTO from already-rendered YAML + body."""
        if not body_markdown.strip():
            raise ValueError("body_markdown must be non-empty")
        body_stripped = body_markdown.lstrip("\n")
        markdown = (
            _FRONT_MATTER_DELIMITER
            + front_matter_yaml.rstrip("\n")
            + "\n"
            + _FRONT_MATTER_DELIMITER
            + "\n"
            + body_stripped
        )
        return cls(
            doc_id=doc_id,
            card_version=card_version,
            markdown=markdown,
            front_matter_yaml=front_matter_yaml.rstrip("\n"),
            body_markdown=body_stripped,
        )

    @classmethod
    def parse(cls, *, doc_id: str, card_version: str, markdown: str) -> RAGCardMarkdownDTO:
        """Parse existing Markdown document into front matter + body."""
        if not markdown.startswith(_FRONT_MATTER_DELIMITER):
            raise MalformedFrontMatterError(
                "markdown must start with '---\\n' front matter delimiter"
            )
        parts = markdown.split(_FRONT_MATTER_DELIMITER, 2)
        if len(parts) < 3:
            raise MalformedFrontMatterError(
                "markdown must contain closing '---\\n' front matter delimiter"
            )
        front = parts[1].rstrip("\n")
        body = parts[2].lstrip("\n")
        if not body:
            raise ValueError("body_markdown must be non-empty")
        return cls(
            doc_id=doc_id,
            card_version=card_version,
            markdown=markdown,
            front_matter_yaml=front,
            body_markdown=body,
        )
