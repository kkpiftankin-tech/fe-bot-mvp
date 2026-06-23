"""Unit tests for RAGCardEditLockDTO (SETUP-06 / T-S06-005)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from schemas.setup.rag_card_edit_lock import EditLockStatus, RAGCardEditLockDTO


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(**overrides: object) -> RAGCardEditLockDTO:
    defaults: dict[str, object] = {
        "lock_id": "lock_001",
        "doc_id": "schema.x.v1",
        "card_version": "1.0",
        "locked_by": "u1",
        "locked_at": _now(),
        "expires_at": _now() + timedelta(minutes=5),
    }
    defaults.update(overrides)
    return RAGCardEditLockDTO(**defaults)  # type: ignore[arg-type]


def test_default_status_active():
    lock = _make()
    assert lock.status == EditLockStatus.ACTIVE


def test_is_expired_false_when_future():
    lock = _make()
    assert lock.is_expired(_now()) is False


def test_is_expired_true_when_past():
    lock = _make(expires_at=_now() - timedelta(seconds=1))
    assert lock.is_expired(_now()) is True


def test_dto_is_frozen():
    lock = _make()
    with pytest.raises(ValidationError):
        lock.status = EditLockStatus.RELEASED  # type: ignore[misc]


def test_status_enum_values():
    assert {s.value for s in EditLockStatus} == {"active", "released", "expired"}


def test_card_version_pattern():
    with pytest.raises(ValidationError):
        _make(card_version="x")
