"""ClassifierTree — snapshot всего дерева библиотеки классификаторов.

SETUP-13 / ADR-HTC-09.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.classifier.node import ClassifierNode


class ClassifierTree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tree_id: str = Field(..., min_length=1, max_length=64)
    version: str = Field(default="1.0.0")
    description: str = Field(default="", max_length=1024)
    nodes: dict[str, ClassifierNode] = Field(default_factory=dict)
    root_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistency(self) -> ClassifierTree:
        for node_id, node in self.nodes.items():
            if node.node_id != node_id:
                raise ValueError(
                    f"nodes key {node_id!r} != node.node_id {node.node_id!r}"
                )
            if node.parent_id is not None and node.parent_id not in self.nodes:
                raise ValueError(
                    f"node {node_id!r}: parent_id {node.parent_id!r} not in tree"
                )
            for child_id in node.children_ids:
                if child_id not in self.nodes:
                    raise ValueError(
                        f"node {node_id!r}: child {child_id!r} not in tree"
                    )
                if self.nodes[child_id].parent_id != node_id:
                    raise ValueError(
                        f"child {child_id!r} parent_id does not point back to {node_id!r}"
                    )
        for root_id in self.root_ids:
            if root_id not in self.nodes:
                raise ValueError(f"root_id {root_id!r} not in tree")
            if self.nodes[root_id].parent_id is not None:
                raise ValueError(f"root {root_id!r} must have parent_id=None")
        return self

    def get_children(self, node_id: str) -> list[ClassifierNode]:
        node = self.nodes[node_id]
        return [self.nodes[cid] for cid in node.children_ids]

    def get_path(self, node_id: str) -> list[str]:
        """Список имён от корня до ``node_id`` включительно."""
        path: list[str] = []
        current: str | None = node_id
        while current is not None:
            node = self.nodes[current]
            path.append(node.name)
            current = node.parent_id
        return list(reversed(path))
