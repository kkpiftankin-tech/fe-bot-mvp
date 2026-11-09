"""Component-тесты ClassifierTreeService (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import pytest
from schemas.classifier.node import ClassifierNode
from schemas.classifier.tree import ClassifierTree

from fe_bot.classifier.tree_repository import (
    ClassifierTreeRepository,
    NoActiveTreeError,
    TreeNotFoundError,
)
from fe_bot.classifier.tree_service import (
    ClassifierTreeService,
    NodeNotFoundError,
    RootDeletionError,
)

pytestmark = pytest.mark.component


def _base_tree() -> ClassifierTree:
    root = ClassifierNode(
        node_id="root", parent_id=None, level=-1, name="АСУ", children_ids=["task"]
    )
    task = ClassifierNode(
        node_id="task", parent_id="root", level=0, name="Задача", children_ids=["purpose"]
    )
    purpose = ClassifierNode(
        node_id="purpose", parent_id="task", level=1, name="Назначение", children_ids=[]
    )
    return ClassifierTree(
        tree_id="t1",
        nodes={"root": root, "task": task, "purpose": purpose},
        root_ids=["root"],
    )


@pytest.fixture
def service() -> ClassifierTreeService:
    repo = ClassifierTreeRepository()
    svc = ClassifierTreeService(repo)
    svc.import_tree(_base_tree())
    return svc


class TestRepository:
    def test_no_active_tree_raises(self) -> None:
        repo = ClassifierTreeRepository()
        with pytest.raises(NoActiveTreeError):
            repo.get_active()

    def test_unknown_tree_id_raises(self) -> None:
        repo = ClassifierTreeRepository()
        with pytest.raises(TreeNotFoundError):
            repo.get("ghost")

    def test_snapshot_restore_roundtrip(self) -> None:
        repo = ClassifierTreeRepository()
        repo.save(_base_tree(), make_active=True)
        snap = repo.snapshot()

        restored = ClassifierTreeRepository()
        restored.restore(snap)
        assert restored.get_active().tree_id == "t1"
        assert restored.get("t1").nodes["purpose"].name == "Назначение"


class TestAddChild:
    def test_add_child_appears_under_parent(self, service: ClassifierTreeService) -> None:
        updated = service.add_child("t1", parent_id="purpose", name="Цель управления")
        purpose = updated.nodes["purpose"]
        assert len(purpose.children_ids) == 1
        new_id = purpose.children_ids[0]
        assert updated.nodes[new_id].name == "Цель управления"
        assert updated.nodes[new_id].level == 2
        assert updated.nodes[new_id].parent_id == "purpose"

    def test_add_child_makes_former_leaf_a_branch(self, service: ClassifierTreeService) -> None:
        assert service.get_tree("t1").nodes["purpose"].is_leaf is True
        updated = service.add_child("t1", parent_id="purpose", name="X")
        assert updated.nodes["purpose"].is_leaf is False

    def test_add_child_to_unknown_parent_raises(self, service: ClassifierTreeService) -> None:
        with pytest.raises(NodeNotFoundError):
            service.add_child("t1", parent_id="ghost", name="X")

    def test_persisted_after_add(self, service: ClassifierTreeService) -> None:
        service.add_child("t1", parent_id="purpose", name="Цель управления")
        reloaded = service.get_tree("t1")
        assert reloaded.nodes["purpose"].children_ids


class TestUpdateNode:
    def test_rename(self, service: ClassifierTreeService) -> None:
        updated = service.update_node("t1", "purpose", name="Новое имя")
        assert updated.nodes["purpose"].name == "Новое имя"

    def test_set_prompt_override(self, service: ClassifierTreeService) -> None:
        updated = service.update_node("t1", "task", prompt_override="CUSTOM")
        assert updated.nodes["task"].prompt_override == "CUSTOM"

    def test_omitting_prompt_override_leaves_it_untouched(
        self, service: ClassifierTreeService
    ) -> None:
        service.update_node("t1", "task", prompt_override="CUSTOM")
        updated = service.update_node("t1", "task", description="desc")
        assert updated.nodes["task"].prompt_override == "CUSTOM"

    def test_explicit_none_clears_prompt_override(self, service: ClassifierTreeService) -> None:
        service.update_node("t1", "task", prompt_override="CUSTOM")
        updated = service.update_node("t1", "task", prompt_override=None)
        assert updated.nodes["task"].prompt_override is None

    def test_unknown_node_raises(self, service: ClassifierTreeService) -> None:
        with pytest.raises(NodeNotFoundError):
            service.update_node("t1", "ghost", name="X")


class TestDeleteNode:
    def test_delete_leaf(self, service: ClassifierTreeService) -> None:
        updated = service.delete_node("t1", "purpose")
        assert "purpose" not in updated.nodes
        assert "purpose" not in updated.nodes["task"].children_ids

    def test_delete_branch_cascades_to_descendants(self, service: ClassifierTreeService) -> None:
        service.add_child("t1", parent_id="purpose", name="Цель управления")
        purpose_children = service.get_tree("t1").nodes["purpose"].children_ids
        goal_id = purpose_children[0]

        updated = service.delete_node("t1", "purpose")
        assert "purpose" not in updated.nodes
        assert goal_id not in updated.nodes  # descendant удалён каскадно

    def test_delete_root_raises(self, service: ClassifierTreeService) -> None:
        with pytest.raises(RootDeletionError):
            service.delete_node("t1", "root")

    def test_delete_unknown_node_raises(self, service: ClassifierTreeService) -> None:
        with pytest.raises(NodeNotFoundError):
            service.delete_node("t1", "ghost")
