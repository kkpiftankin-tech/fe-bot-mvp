"""Unit tests for VersioningService (SETUP-06 / T-S06-016)."""

from __future__ import annotations

from datetime import UTC, datetime

from fe_bot.setup.card_review.versioning import VersioningService
from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard


def _card(version: str = "1.0", **kw: object) -> RAGCard:
    defaults: dict[str, object] = {
        "doc_id": "schema.x.v1",
        "doc_type": DocType.SCHEMA_CARD,
        "title": "Test",
        "version": version,
        "card_version": version,
        "status": CardStatus.REVIEW_REQUIRED,
        "body_markdown": "Some body content here",
        "front_matter": {"retrieval_tags": ["foo"]},
        "source_document_ids": ["src_1"],
        "source_section_ids": ["sec_1"],
        "created_by": "u1",
        "created_at": datetime(2026, 6, 23, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 23, tzinfo=UTC),
    }
    defaults.update(kw)
    return RAGCard(**defaults)  # type: ignore[arg-type]


def test_minor_bump_for_edit():
    v = VersioningService()
    result = v.create_new_version(
        _card("1.0"),
        bump_type="minor",
        change_reason="edit",
        created_by="u1",
        new_card_body="New body content here",
    )
    assert result.new_card.card_version == "1.1"
    assert result.version_dto.card_version == "1.1"
    assert result.version_dto.parent_card_version == "1.0"


def test_major_bump_for_regenerate():
    v = VersioningService()
    result = v.create_new_version(
        _card("1.5"),
        bump_type="major",
        change_reason="regenerate",
        created_by="u1",
    )
    assert result.new_card.card_version == "2.0"
    assert result.version_dto.parent_card_version == "1.5"


def test_new_version_marked_current():
    v = VersioningService()
    result = v.create_new_version(
        _card("1.0"),
        bump_type="minor",
        change_reason=None,
        created_by="u1",
        new_card_body="x" * 50,
    )
    assert result.version_dto.is_current is True


def test_body_hash_sha256_format():
    v = VersioningService()
    result = v.create_new_version(
        _card("1.0"),
        bump_type="minor",
        change_reason=None,
        created_by="u1",
        new_card_body="Some specific body here",
    )
    assert result.version_dto.body_hash.startswith("sha256:")
    assert len(result.version_dto.body_hash) == len("sha256:") + 64


def test_old_card_immutable():
    v = VersioningService()
    old = _card("1.0")
    result = v.create_new_version(
        old, bump_type="minor", change_reason=None, created_by="u1",
        new_card_body="changed body content",
    )
    assert old.card_version == "1.0"  # original untouched
    assert result.new_card.card_version == "1.1"


def test_target_status_default_edited():
    v = VersioningService()
    result = v.create_new_version(
        _card("1.0"), bump_type="minor", change_reason=None, created_by="u1",
        new_card_body="b" * 50,
    )
    assert result.new_card.status == CardStatus.EDITED


def test_custom_target_status():
    v = VersioningService()
    result = v.create_new_version(
        _card("1.0"), bump_type="major", change_reason=None, created_by="u1",
        target_status=CardStatus.GENERATED,
    )
    assert result.new_card.status == CardStatus.GENERATED


def test_metadata_snapshot_persisted():
    v = VersioningService()
    fm = {"retrieval_tags": ["new", "tags"]}
    result = v.create_new_version(
        _card("1.0"), bump_type="minor", change_reason=None, created_by="u1",
        new_front_matter=fm,
    )
    assert result.version_dto.metadata_snapshot == fm
