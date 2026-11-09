"""Unit tests for CardEditorService (SETUP-06 / T-S06-015)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard

from fe_bot.setup.card_review.editor import (
    CardEditorService,
    EmptyEditPayloadError,
    SystemMetadataReadOnlyError,
)


def _card(**kw: object) -> RAGCard:
    defaults: dict[str, object] = {
        "doc_id": "schema.x.v1",
        "doc_type": DocType.SCHEMA_CARD,
        "title": "Original Title",
        "version": "1.0",
        "status": CardStatus.REVIEW_REQUIRED,
        "body_markdown": "Original body content of card",
        "front_matter": {"retrieval_tags": ["foo"], "phase": ["feature_synthesis"]},
        "source_document_ids": ["src_1"],
        "source_section_ids": ["sec_1"],
        "created_by": "u1",
        "created_at": datetime(2026, 6, 23, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 23, tzinfo=UTC),
    }
    defaults.update(kw)
    return RAGCard(**defaults)  # type: ignore[arg-type]


def test_apply_patch_updates_title():
    e = CardEditorService()
    draft = e.apply_patch(_card(), metadata_patch={"title": "New Title"})
    assert draft.card.title == "New Title"
    assert draft.metadata_changed
    assert not draft.body_changed


def test_apply_patch_updates_front_matter():
    e = CardEditorService()
    draft = e.apply_patch(_card(), metadata_patch={"retrieval_tags": ["foo", "bar"]})
    assert draft.card.front_matter["retrieval_tags"] == ["foo", "bar"]
    assert draft.metadata_changed


def test_apply_patch_updates_body():
    e = CardEditorService()
    draft = e.apply_patch(_card(), body_markdown="Completely new body")
    assert draft.card.body_markdown == "Completely new body"
    assert draft.body_changed
    assert not draft.metadata_changed


def test_system_metadata_rejected():
    e = CardEditorService()
    with pytest.raises(SystemMetadataReadOnlyError) as exc_info:
        e.apply_patch(_card(), metadata_patch={"doc_id": "new.id"})
    assert "doc_id" in exc_info.value.fields


def test_unknown_field_ignored():
    e = CardEditorService()
    draft = e.apply_patch(_card(), metadata_patch={"title": "X", "unknown_field": "y"})
    # title applied, unknown silently ignored
    assert draft.card.title == "X"
    assert "unknown_field" not in draft.card.front_matter


def test_empty_payload_raises():
    e = CardEditorService()
    with pytest.raises(EmptyEditPayloadError):
        e.apply_patch(_card())


def test_no_actual_change_raises():
    e = CardEditorService()
    with pytest.raises(EmptyEditPayloadError):
        e.apply_patch(_card(), metadata_patch={"title": "Original Title"})


def test_calculate_diff_title():
    e = CardEditorService()
    old = _card(title="Old")
    new = _card(title="New")
    diff = e.calculate_diff(
        old_card=old, new_card=new, from_version="1.0", to_version="1.1"
    )
    assert any(d.field == "title" for d in diff.metadata_diff)


def test_calculate_diff_body():
    e = CardEditorService()
    old = _card(body_markdown="Original body content here")
    new = _card(body_markdown="Modified body content here")
    diff = e.calculate_diff(
        old_card=old, new_card=new, from_version="1.0", to_version="1.1"
    )
    assert diff.body_diff is not None
    assert "Modified" in diff.body_diff.content


def test_calculate_diff_no_change():
    e = CardEditorService()
    card = _card()
    diff = e.calculate_diff(
        old_card=card, new_card=card, from_version="1.0", to_version="1.0"
    )
    assert diff.body_diff is None
    assert diff.metadata_diff == []


def test_immutability_old_card_not_mutated():
    e = CardEditorService()
    original = _card()
    original_title = original.title
    draft = e.apply_patch(original, metadata_patch={"title": "Changed"})
    assert original.title == original_title  # original unchanged
    assert draft.card.title == "Changed"
