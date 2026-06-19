"""Unit-тесты RAGCardSourceLinkDTO (SETUP-05 / T-S05-005)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.rag_card_source_link import RAGCardSourceLinkDTO

pytestmark = pytest.mark.unit


def _link(**overrides: object) -> RAGCardSourceLinkDTO:
    kwargs: dict[str, object] = {
        "source_link_id": "lnk_001",
        "doc_id": "analytics.x.v1",
        "card_version": "1.0",
        "source_document_id": "src_001",
        "source_section_id": "sec_001",
        "created_at": datetime(2026, 6, 19, tzinfo=UTC),
    }
    kwargs.update(overrides)
    return RAGCardSourceLinkDTO(**kwargs)


class TestSourceLink:
    def test_default_relation_generated_from(self) -> None:
        link = _link()
        assert link.relation_type == LineageRelationType.GENERATED_FROM

    def test_frozen(self) -> None:
        link = _link()
        with pytest.raises(ValidationError):
            link.metadata = {"new": "value"}  # type: ignore[misc]

    def test_lineage_enum_includes_rag_card(self) -> None:
        assert LineageTargetType.RAG_CARD.value == "rag_card"
        assert LineageRelationType.GENERATED_FROM.value == "generated_from"
