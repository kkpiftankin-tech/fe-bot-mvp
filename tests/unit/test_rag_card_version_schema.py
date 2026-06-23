"""Unit tests for RAGCardVersionDTO (SETUP-06 / T-S06-003)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas.rag.rag_card import CardStatus
from schemas.setup.rag_card_version import RAGCardVersionDTO, bump_version


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


_HASH = "sha256:" + "a" * 64


def _make(**overrides: object) -> RAGCardVersionDTO:
    defaults: dict[str, object] = {
        "doc_id": "schema.x.v1",
        "card_version": "1.0",
        "status": CardStatus.GENERATED,
        "markdown_artifact_id": "art_001",
        "body_hash": _HASH,
        "created_by": "u1",
        "created_at": _now(),
    }
    defaults.update(overrides)
    return RAGCardVersionDTO(**defaults)  # type: ignore[arg-type]


def test_bump_minor():
    assert bump_version("1.0", bump_type="minor") == "1.1"
    assert bump_version("1.5", bump_type="minor") == "1.6"
    assert bump_version("2.9", bump_type="minor") == "2.10"


def test_bump_major():
    assert bump_version("1.0", bump_type="major") == "2.0"
    assert bump_version("1.5", bump_type="major") == "2.0"
    assert bump_version("9.3", bump_type="major") == "10.0"


def test_bump_invalid_version():
    with pytest.raises(ValueError):
        bump_version("vX", bump_type="minor")


def test_bump_invalid_type():
    with pytest.raises(ValueError):
        bump_version("1.0", bump_type="patch")


def test_dto_happy_path():
    v = _make()
    assert v.card_version == "1.0"
    assert v.is_current is False
    assert v.body_hash.startswith("sha256:")


def test_dto_with_parent():
    v = _make(parent_card_version="1.0", card_version="1.1")
    assert v.parent_card_version == "1.0"


def test_dto_is_frozen():
    v = _make()
    with pytest.raises(ValidationError):
        v.is_current = True  # type: ignore[misc]


def test_card_version_pattern():
    with pytest.raises(ValidationError):
        _make(card_version="1")


def test_body_hash_pattern():
    with pytest.raises(ValidationError):
        _make(body_hash="md5:abc")


def test_metadata_snapshot_default():
    v = _make()
    assert v.metadata_snapshot == {}
