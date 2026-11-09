"""Unit tests for EditLockRepository (SETUP-06 / T-S06-010)."""

from __future__ import annotations

import time

import pytest
from schemas.setup.rag_card_edit_lock import EditLockStatus

from fe_bot.setup.card_review.edit_lock_repository import (
    EditLockActiveError,
    EditLockNotFoundError,
    EditLockReleaseDeniedError,
    InMemoryEditLockRepository,
)


def test_acquire_happy_path():
    repo = InMemoryEditLockRepository()
    lock = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=60)
    assert lock.locked_by == "u1"
    assert lock.status == EditLockStatus.ACTIVE


def test_acquire_by_same_user_returns_existing():
    repo = InMemoryEditLockRepository()
    lock1 = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=60)
    lock2 = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=60)
    assert lock1.lock_id == lock2.lock_id


def test_acquire_conflict_different_user():
    repo = InMemoryEditLockRepository()
    repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=60)
    with pytest.raises(EditLockActiveError) as exc_info:
        repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u2", ttl_seconds=60)
    assert exc_info.value.active_lock.locked_by == "u1"


def test_release_by_owner():
    repo = InMemoryEditLockRepository()
    lock = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=60)
    repo.release(lock.lock_id, released_by="u1")
    assert repo.get_active("a.v1") is None


def test_release_by_other_denied():
    repo = InMemoryEditLockRepository()
    lock = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=60)
    with pytest.raises(EditLockReleaseDeniedError):
        repo.release(lock.lock_id, released_by="u2")


def test_release_admin_override():
    repo = InMemoryEditLockRepository()
    lock = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=60)
    repo.release(lock.lock_id, released_by="admin1", admin_override=True)
    assert repo.get_active("a.v1") is None


def test_release_missing_raises():
    repo = InMemoryEditLockRepository()
    with pytest.raises(EditLockNotFoundError):
        repo.release("nope", released_by="u1")


def test_get_active_when_no_lock():
    repo = InMemoryEditLockRepository()
    assert repo.get_active("a.v1") is None


def test_expired_lock_cleanup():
    repo = InMemoryEditLockRepository()
    lock = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=0)
    # Lock expires immediately (ttl=0 → expires_at ≈ now).
    time.sleep(0.01)
    expired = repo.cleanup_expired()
    assert lock.lock_id in {e.lock_id for e in expired}
    assert repo.get_active("a.v1") is None


def test_acquire_after_expiry_succeeds_for_other_user():
    repo = InMemoryEditLockRepository()
    repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u1", ttl_seconds=0)
    time.sleep(0.01)
    new_lock = repo.acquire(doc_id="a.v1", card_version="1.0", locked_by="u2", ttl_seconds=60)
    assert new_lock.locked_by == "u2"
