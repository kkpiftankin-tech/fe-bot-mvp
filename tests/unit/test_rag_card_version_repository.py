"""Unit tests for RAGCardVersionRepository (SETUP-06 / T-S06-009)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.rag.rag_card import CardStatus
from schemas.setup.rag_card_version import RAGCardVersionDTO

from fe_bot.setup.card_review.version_repository import (
    CardVersionAlreadyExistsError,
    CardVersionNotFoundError,
    InMemoryRAGCardVersionRepository,
)


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


_HASH = "sha256:" + "b" * 64


def _make(doc_id: str = "schema.x.v1", card_version: str = "1.0", **kw: object) -> RAGCardVersionDTO:
    defaults: dict[str, object] = {
        "doc_id": doc_id,
        "card_version": card_version,
        "status": CardStatus.GENERATED,
        "markdown_artifact_id": "art_1",
        "body_hash": _HASH,
        "created_by": "u1",
        "created_at": _now(),
    }
    defaults.update(kw)
    return RAGCardVersionDTO(**defaults)  # type: ignore[arg-type]


def test_add_and_get():
    repo = InMemoryRAGCardVersionRepository()
    v = _make()
    repo.add(v)
    assert repo.get("schema.x.v1", "1.0").doc_id == "schema.x.v1"


def test_add_duplicate_raises():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make())
    with pytest.raises(CardVersionAlreadyExistsError):
        repo.add(_make())


def test_get_missing_raises():
    repo = InMemoryRAGCardVersionRepository()
    with pytest.raises(CardVersionNotFoundError):
        repo.get("x", "1.0")


def test_list_for_card_filters():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make(doc_id="a", card_version="1.0"))
    repo.add(_make(doc_id="a", card_version="1.1"))
    repo.add(_make(doc_id="b", card_version="1.0"))
    versions = repo.list_for_card("a")
    assert {v.card_version for v in versions} == {"1.0", "1.1"}


def test_current_returns_none_if_no_current():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make())
    assert repo.current("schema.x.v1") is None


def test_set_current_invariant_single_current():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make(card_version="1.0"))
    repo.add(_make(card_version="1.1"))
    repo.set_current("schema.x.v1", "1.0")
    current = repo.current("schema.x.v1")
    assert current is not None
    assert current.card_version == "1.0"

    repo.set_current("schema.x.v1", "1.1")
    current = repo.current("schema.x.v1")
    assert current is not None
    assert current.card_version == "1.1"
    # 1.0 теперь не current
    assert repo.get("schema.x.v1", "1.0").is_current is False


def test_add_with_is_current_true_unsets_others():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make(card_version="1.0", is_current=True))
    repo.add(_make(card_version="1.1", is_current=True))
    assert repo.get("schema.x.v1", "1.0").is_current is False
    assert repo.get("schema.x.v1", "1.1").is_current is True


def test_mark_deprecated():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make(card_version="1.0", is_current=True))
    repo.mark_deprecated("schema.x.v1", "1.0")
    v = repo.get("schema.x.v1", "1.0")
    assert v.status == CardStatus.DEPRECATED
    assert v.is_current is False


def test_set_current_missing_raises():
    repo = InMemoryRAGCardVersionRepository()
    with pytest.raises(CardVersionNotFoundError):
        repo.set_current("schema.x.v1", "1.0")


def test_snapshot_restore_preserves_current_flag():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make(card_version="1.0", is_current=True))
    repo.add(_make(card_version="1.1"))
    data = repo.snapshot()

    repo2 = InMemoryRAGCardVersionRepository()
    repo2.restore(data)
    current = repo2.current("schema.x.v1")
    assert current is not None and current.card_version == "1.0"


def test_clear():
    repo = InMemoryRAGCardVersionRepository()
    repo.add(_make())
    repo.clear()
    with pytest.raises(CardVersionNotFoundError):
        repo.get("schema.x.v1", "1.0")
