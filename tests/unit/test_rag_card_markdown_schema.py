"""Unit-тесты RAGCardMarkdownDTO (SETUP-05 / T-S05-004)."""

from __future__ import annotations

import pytest
from schemas.setup.rag_card_markdown import (
    MalformedFrontMatterError,
    RAGCardMarkdownDTO,
)

pytestmark = pytest.mark.unit

_YAML = "doc_id: analytics.x.v1\ndoc_type: analytics_card"
_BODY = "# Sensor analytics\n\nDescription."


class TestFromParts:
    def test_build_from_parts(self) -> None:
        dto = RAGCardMarkdownDTO.from_parts(
            doc_id="analytics.x.v1",
            card_version="1.0",
            front_matter_yaml=_YAML,
            body_markdown=_BODY,
        )
        assert dto.markdown.startswith("---\n")
        assert "doc_type: analytics_card" in dto.markdown
        assert dto.body_markdown == _BODY

    def test_empty_body_raises(self) -> None:
        with pytest.raises(ValueError, match="body_markdown must be non-empty"):
            RAGCardMarkdownDTO.from_parts(
                doc_id="x",
                card_version="1.0",
                front_matter_yaml=_YAML,
                body_markdown="   \n",
            )


class TestParse:
    def test_roundtrip(self) -> None:
        dto = RAGCardMarkdownDTO.from_parts(
            doc_id="analytics.x.v1",
            card_version="1.0",
            front_matter_yaml=_YAML,
            body_markdown=_BODY,
        )
        parsed = RAGCardMarkdownDTO.parse(
            doc_id="analytics.x.v1",
            card_version="1.0",
            markdown=dto.markdown,
        )
        assert parsed.body_markdown == _BODY
        assert "doc_type: analytics_card" in parsed.front_matter_yaml

    def test_missing_front_matter_raises(self) -> None:
        with pytest.raises(MalformedFrontMatterError):
            RAGCardMarkdownDTO.parse(
                doc_id="x",
                card_version="1.0",
                markdown="No front matter here",
            )

    def test_missing_closing_delimiter_raises(self) -> None:
        with pytest.raises(MalformedFrontMatterError):
            RAGCardMarkdownDTO.parse(
                doc_id="x",
                card_version="1.0",
                markdown="---\ndoc_id: x\nstill yaml...\nno closing",
            )


class TestValidation:
    def test_inconsistent_front_matter_raises(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RAGCardMarkdownDTO(
                doc_id="x",
                card_version="1.0",
                markdown="---\nactual: yaml\n---\n\nbody",
                front_matter_yaml="different: yaml",
                body_markdown="body",
            )
