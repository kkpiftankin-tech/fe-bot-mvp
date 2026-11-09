"""In-memory репозиторий ClassifierTree (SETUP-13 / ADR-HTC-09).

Паттерн — как у остальных in-memory repo проекта (см.
src/fe_bot/taxonomy/version_repository.py): dict-backend, готов к
замене на PostgreSQL. ``snapshot()``/``restore()`` совместимы с
``fe_bot.persistence.snapshot.SnapshotPersister`` (dev-only JSON
persistence, см. src/fe_bot/persistence/snapshot.py).
"""

from __future__ import annotations

from typing import Any

from schemas.classifier.tree import ClassifierTree


class TreeNotFoundError(LookupError):
    def __init__(self, tree_id: str) -> None:
        self.tree_id = tree_id
        super().__init__(f"ClassifierTree not found: {tree_id}")


class NoActiveTreeError(LookupError):
    def __init__(self) -> None:
        super().__init__("No active ClassifierTree — import one first")


class ClassifierTreeRepository:
    def __init__(self) -> None:
        self._trees: dict[str, ClassifierTree] = {}
        self._active_tree_id: str | None = None

    def save(self, tree: ClassifierTree, *, make_active: bool = False) -> None:
        self._trees[tree.tree_id] = tree
        if make_active or self._active_tree_id is None:
            self._active_tree_id = tree.tree_id

    def get(self, tree_id: str) -> ClassifierTree:
        if tree_id not in self._trees:
            raise TreeNotFoundError(tree_id)
        return self._trees[tree_id]

    def get_active(self) -> ClassifierTree:
        if self._active_tree_id is None:
            raise NoActiveTreeError()
        return self.get(self._active_tree_id)

    def list_ids(self) -> list[str]:
        return sorted(self._trees.keys())

    # ----- SnapshotPersister protocol -----

    def snapshot(self) -> dict[str, Any]:
        return {
            "active_tree_id": self._active_tree_id,
            "trees": {tid: t.model_dump(mode="json") for tid, t in self._trees.items()},
        }

    def restore(self, data: dict[str, Any]) -> None:
        self._trees = {
            tid: ClassifierTree.model_validate(payload)
            for tid, payload in data.get("trees", {}).items()
        }
        self._active_tree_id = data.get("active_tree_id")
