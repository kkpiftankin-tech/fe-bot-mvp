"""Lightweight JSON snapshot persistence for dev (no DB).

См. ``src/fe_bot/persistence/snapshot.py``.
"""

from fe_bot.persistence.snapshot import (
    SnapshotPersister,
    register_default_state,
)

__all__ = ["SnapshotPersister", "register_default_state"]
