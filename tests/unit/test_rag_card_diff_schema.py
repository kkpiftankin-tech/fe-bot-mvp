"""Unit tests for RAGCardDiffDTO (SETUP-06 / T-S06-004)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from schemas.setup.rag_card_diff import BodyDiff, MetadataFieldDiff, RAGCardDiffDTO


def test_metadata_field_diff_happy():
    diff = MetadataFieldDiff(field="retrieval_tags", old_value=["a"], new_value=["a", "b"])
    assert diff.field == "retrieval_tags"
    assert diff.new_value == ["a", "b"]


def test_metadata_field_diff_frozen():
    diff = MetadataFieldDiff(field="title", old_value="old", new_value="new")
    with pytest.raises(ValidationError):
        diff.field = "x"  # type: ignore[misc]


def test_body_diff_default_unified():
    bd = BodyDiff(content="--- a\n+++ b\n@@ ...")
    assert bd.format == "unified"


def test_dto_empty_diffs_ok():
    dto = RAGCardDiffDTO(
        doc_id="schema.x.v1",
        from_version="1.0",
        to_version="1.1",
    )
    assert dto.metadata_diff == []
    assert dto.body_diff is None


def test_dto_with_metadata_and_body():
    dto = RAGCardDiffDTO(
        doc_id="schema.x.v1",
        from_version="1.0",
        to_version="1.1",
        metadata_diff=[
            MetadataFieldDiff(field="title", old_value="A", new_value="B"),
        ],
        body_diff=BodyDiff(content="diff body"),
    )
    assert len(dto.metadata_diff) == 1
    assert dto.body_diff is not None
    assert dto.body_diff.content == "diff body"


def test_version_pattern():
    with pytest.raises(ValidationError):
        RAGCardDiffDTO(
            doc_id="schema.x.v1",
            from_version="latest",
            to_version="1.1",
        )
