"""ClassifierTreeService — CRUD над деревом классификаторов.

SETUP-13 / ADR-HTC-09. Каждая мутация строит НОВЫЙ ``ClassifierTree``
через конструктор (не ``model_copy``) — это гарантирует, что
tree-level ``model_validator`` (согласованность parent/children)
проверяется заново после каждого изменения, а не может незаметно
разъехаться.
"""

from __future__ import annotations

from schemas.classifier.node import ClassifierNode
from schemas.classifier.tree import ClassifierTree

from fe_bot.classifier.slug import slugify
from fe_bot.classifier.tree_repository import ClassifierTreeRepository


class NodeNotFoundError(LookupError):
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__(f"ClassifierNode not found: {node_id}")


class RootDeletionError(ValueError):
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        super().__init__(f"Cannot delete root node: {node_id}")


class _Unset:
    """Sentinel: отличает «параметр не передан» от «передан None»."""


_UNSET = _Unset()


def _collect_descendants(tree: ClassifierTree, node_id: str) -> set[str]:
    """node_id + все узлы под ним (включительно)."""
    result: set[str] = set()
    stack = [node_id]
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.add(current)
        stack.extend(tree.nodes[current].children_ids)
    return result


class ClassifierTreeService:
    def __init__(self, repo: ClassifierTreeRepository) -> None:
        self._repo = repo

    def get_tree(self, tree_id: str) -> ClassifierTree:
        return self._repo.get(tree_id)

    def get_active_tree(self) -> ClassifierTree:
        return self._repo.get_active()

    def import_tree(self, tree: ClassifierTree, *, make_active: bool = True) -> ClassifierTree:
        self._repo.save(tree, make_active=make_active)
        return tree

    def add_child(
        self,
        tree_id: str,
        *,
        parent_id: str,
        name: str,
        description: str = "",
    ) -> ClassifierTree:
        tree = self._repo.get(tree_id)
        if parent_id not in tree.nodes:
            raise NodeNotFoundError(parent_id)
        parent = tree.nodes[parent_id]
        node_id = slugify(name, set(tree.nodes.keys()))

        new_node = ClassifierNode(
            node_id=node_id,
            parent_id=parent_id,
            level=parent.level + 1,
            name=name,
            description=description,
        )
        new_nodes = dict(tree.nodes)
        new_nodes[node_id] = new_node
        new_nodes[parent_id] = parent.model_copy(
            update={"children_ids": [*parent.children_ids, node_id]}
        )
        updated = ClassifierTree(
            tree_id=tree.tree_id,
            version=tree.version,
            description=tree.description,
            nodes=new_nodes,
            root_ids=tree.root_ids,
        )
        self._repo.save(updated)
        return updated

    def update_node(
        self,
        tree_id: str,
        node_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        prompt_override: str | None | _Unset = _UNSET,
    ) -> ClassifierTree:
        """``prompt_override``: не передавай, чтобы оставить как есть;
        передай ``None`` явно, чтобы сбросить override на общий шаблон."""
        tree = self._repo.get(tree_id)
        if node_id not in tree.nodes:
            raise NodeNotFoundError(node_id)
        node = tree.nodes[node_id]
        update: dict[str, object] = {}
        if name is not None:
            update["name"] = name
        if description is not None:
            update["description"] = description
        if not isinstance(prompt_override, _Unset):
            update["prompt_override"] = prompt_override
        new_nodes = dict(tree.nodes)
        new_nodes[node_id] = node.model_copy(update=update)
        updated = ClassifierTree(
            tree_id=tree.tree_id,
            version=tree.version,
            description=tree.description,
            nodes=new_nodes,
            root_ids=tree.root_ids,
        )
        self._repo.save(updated)
        return updated

    def delete_node(self, tree_id: str, node_id: str) -> ClassifierTree:
        tree = self._repo.get(tree_id)
        if node_id not in tree.nodes:
            raise NodeNotFoundError(node_id)
        if node_id in tree.root_ids:
            raise RootDeletionError(node_id)

        to_remove = _collect_descendants(tree, node_id)
        new_nodes = {nid: n for nid, n in tree.nodes.items() if nid not in to_remove}
        parent_id = tree.nodes[node_id].parent_id
        if parent_id is not None and parent_id in new_nodes:
            parent = new_nodes[parent_id]
            new_nodes[parent_id] = parent.model_copy(
                update={
                    "children_ids": [c for c in parent.children_ids if c != node_id]
                }
            )
        updated = ClassifierTree(
            tree_id=tree.tree_id,
            version=tree.version,
            description=tree.description,
            nodes=new_nodes,
            root_ids=tree.root_ids,
        )
        self._repo.save(updated)
        return updated
