"""Unit-тесты schemas.classifier (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from schemas.classifier.node import ClassifierNode
from schemas.classifier.tree import ClassifierTree

pytestmark = pytest.mark.unit


def _leaf(node_id: str, parent_id: str, level: int, name: str) -> ClassifierNode:
    return ClassifierNode(node_id=node_id, parent_id=parent_id, level=level, name=name)


def _branch(
    node_id: str, parent_id: str | None, level: int, name: str, children_ids: list[str]
) -> ClassifierNode:
    return ClassifierNode(
        node_id=node_id,
        parent_id=parent_id,
        level=level,
        name=name,
        children_ids=children_ids,
    )


class TestClassifierNode:
    def test_leaf_has_no_children(self) -> None:
        node = _leaf("n1", "root", 1, "Цель управления")
        assert node.is_leaf is True

    def test_branch_is_not_leaf(self) -> None:
        node = _branch("n1", None, 0, "Задача", ["n2", "n3"])
        assert node.is_leaf is False

    def test_root_has_no_parent(self) -> None:
        node = _branch("root", None, 0, "АСУ", ["n1"])
        assert node.parent_id is None

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClassifierNode(node_id="n1", level=0, name="X", bogus="y")  # type: ignore[call-arg]


class TestClassifierTree:
    def _small_tree(self) -> ClassifierTree:
        root = _branch("root", None, 0, "АСУ", ["task"])
        task = _branch("task", "root", 1, "Задача", ["purpose"])
        purpose = _leaf("purpose", "task", 2, "Назначение")
        return ClassifierTree(
            tree_id="t1",
            nodes={"root": root, "task": task, "purpose": purpose},
            root_ids=["root"],
        )

    def test_valid_tree_constructs(self) -> None:
        tree = self._small_tree()
        assert tree.nodes["task"].is_leaf is False
        assert tree.nodes["purpose"].is_leaf is True

    def test_get_children(self) -> None:
        tree = self._small_tree()
        children = tree.get_children("task")
        assert [c.node_id for c in children] == ["purpose"]

    def test_get_path(self) -> None:
        tree = self._small_tree()
        assert tree.get_path("purpose") == ["АСУ", "Задача", "Назначение"]

    def test_dangling_child_reference_rejected(self) -> None:
        root = _branch("root", None, 0, "АСУ", ["missing"])
        with pytest.raises(ValidationError, match="not in tree"):
            ClassifierTree(tree_id="t1", nodes={"root": root}, root_ids=["root"])

    def test_parent_child_backreference_mismatch_rejected(self) -> None:
        root = _branch("root", None, 0, "АСУ", ["task"])
        # task.parent_id указывает не на root — несогласованность.
        task = _branch("task", "other", 1, "Задача", [])
        with pytest.raises(ValidationError, match="does not point back"):
            ClassifierTree(
                tree_id="t1", nodes={"root": root, "task": task}, root_ids=["root"]
            )

    def test_root_with_parent_rejected(self) -> None:
        # "ghost" реально существует в дереве — иначе сработает более общая
        # проверка "parent_id not in tree", а не именно root-инвариант.
        ghost = _branch("ghost", None, 0, "Ghost", ["root"])
        root = _branch("root", "ghost", 1, "АСУ", [])
        with pytest.raises(ValidationError, match="parent_id=None"):
            ClassifierTree(
                tree_id="t1",
                nodes={"ghost": ghost, "root": root},
                root_ids=["root"],
            )

    def test_root_id_not_in_nodes_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not in tree"):
            ClassifierTree(tree_id="t1", nodes={}, root_ids=["ghost"])
