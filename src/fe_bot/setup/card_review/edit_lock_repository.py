"""EditLockRepository (SETUP-06 / T-S06-010).

Lock на редактирование RAG-карточки. TTL-based. Один active lock per doc_id.

В MVP — in-memory. Production: Redis с TTL.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

from schemas.setup.rag_card_edit_lock import EditLockStatus, RAGCardEditLockDTO


class EditLockActiveError(RuntimeError):
    """Попытка acquire поверх активного lock другим пользователем."""

    def __init__(self, active_lock: RAGCardEditLockDTO) -> None:
        self.active_lock = active_lock
        super().__init__(
            f"Edit lock active on {active_lock.doc_id!r} by {active_lock.locked_by!r} "
            f"until {active_lock.expires_at.isoformat()}"
        )


class EditLockNotFoundError(KeyError):
    def __init__(self, lock_id: str) -> None:
        self.lock_id = lock_id
        super().__init__(f"EditLock {lock_id!r} not found")


class EditLockReleaseDeniedError(PermissionError):
    """Не владелец lock пытается release без admin override."""

    def __init__(self, lock_id: str, requester: str, owner: str) -> None:
        self.lock_id = lock_id
        self.requester = requester
        self.owner = owner
        super().__init__(
            f"User {requester!r} cannot release EditLock {lock_id!r} owned by {owner!r}"
        )


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _gen_id() -> str:
    return f"lock_{uuid.uuid4().hex[:12]}"


class EditLockRepository(Protocol):
    def acquire(
        self,
        *,
        doc_id: str,
        card_version: str,
        locked_by: str,
        ttl_seconds: int,
    ) -> RAGCardEditLockDTO: ...

    def release(
        self,
        lock_id: str,
        *,
        released_by: str,
        admin_override: bool = False,
    ) -> None: ...

    def get_active(self, doc_id: str) -> RAGCardEditLockDTO | None: ...

    def cleanup_expired(self) -> list[RAGCardEditLockDTO]: ...


class InMemoryEditLockRepository:
    """In-memory + thread-safe + TTL."""

    def __init__(self) -> None:
        self._by_id: dict[str, RAGCardEditLockDTO] = {}
        self._lock = threading.Lock()

    def acquire(
        self,
        *,
        doc_id: str,
        card_version: str,
        locked_by: str,
        ttl_seconds: int = 600,
    ) -> RAGCardEditLockDTO:
        now = _now()
        with self._lock:
            # Cleanup expired before checking.
            self._cleanup_locked(now)
            for existing in self._by_id.values():
                if (
                    existing.doc_id == doc_id
                    and existing.status == EditLockStatus.ACTIVE
                    and not existing.is_expired(now)
                ):
                    if existing.locked_by == locked_by:
                        # Re-acquire by same user — return existing lock.
                        return existing
                    raise EditLockActiveError(existing)
            new_lock = RAGCardEditLockDTO(
                lock_id=_gen_id(),
                doc_id=doc_id,
                card_version=card_version,
                locked_by=locked_by,
                locked_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
                status=EditLockStatus.ACTIVE,
            )
            self._by_id[new_lock.lock_id] = new_lock
            return new_lock

    def release(
        self,
        lock_id: str,
        *,
        released_by: str,
        admin_override: bool = False,
    ) -> None:
        with self._lock:
            lock = self._by_id.get(lock_id)
            if lock is None:
                raise EditLockNotFoundError(lock_id)
            if lock.locked_by != released_by and not admin_override:
                raise EditLockReleaseDeniedError(lock_id, released_by, lock.locked_by)
            self._by_id[lock_id] = lock.model_copy(update={"status": EditLockStatus.RELEASED})

    def get_active(self, doc_id: str) -> RAGCardEditLockDTO | None:
        now = _now()
        with self._lock:
            for lock in self._by_id.values():
                if (
                    lock.doc_id == doc_id
                    and lock.status == EditLockStatus.ACTIVE
                    and not lock.is_expired(now)
                ):
                    return lock
            return None

    def cleanup_expired(self) -> list[RAGCardEditLockDTO]:
        now = _now()
        with self._lock:
            return self._cleanup_locked(now)

    def _cleanup_locked(self, now: datetime) -> list[RAGCardEditLockDTO]:
        # caller holds lock
        released: list[RAGCardEditLockDTO] = []
        for lock_id, lock in list(self._by_id.items()):
            if lock.status == EditLockStatus.ACTIVE and lock.is_expired(now):
                expired = lock.model_copy(update={"status": EditLockStatus.EXPIRED})
                self._by_id[lock_id] = expired
                released.append(expired)
        return released

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()

    # ----- Snapshot -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {lid: lock.model_dump(mode="json") for lid, lock in self._by_id.items()}

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._by_id.clear()
            for lid, raw in data.items():
                self._by_id[lid] = RAGCardEditLockDTO.model_validate(raw)
