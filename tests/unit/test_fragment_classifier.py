"""Unit-тесты FragmentClassifier (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import pytest
from schemas.classifier.node import ClassifierNode
from schemas.classifier.tree import ClassifierTree

from fe_bot.classifier.fragment_classifier import FragmentClassifier
from fe_bot.classifier.prompt_renderer import ClassifierPromptRenderer
from fe_bot.classifier.tree_repository import ClassifierTreeRepository
from fe_bot.classifier.tree_service import ClassifierTreeService
from fe_bot.llm_gateway.client import LLMCallResult, StructuredCallResult

pytestmark = pytest.mark.unit


def _tree() -> ClassifierTree:
    root = ClassifierNode(
        node_id="root", parent_id=None, level=-1, name="АСУ", children_ids=["task", "leaf_root"]
    )
    task = ClassifierNode(
        node_id="task", parent_id="root", level=0, name="Задача",
        children_ids=["purpose", "problem"],
    )
    purpose = ClassifierNode(
        node_id="purpose", parent_id="task", level=1, name="Назначение",
        children_ids=["sub_purpose"],
    )
    sub_purpose = ClassifierNode(
        node_id="sub_purpose", parent_id="purpose", level=2, name="Подназначение", children_ids=[]
    )
    problem = ClassifierNode(
        node_id="problem", parent_id="task", level=1, name="Проблематика", children_ids=[]
    )
    leaf_root = ClassifierNode(
        node_id="leaf_root", parent_id="root", level=0, name="Одинокий лист", children_ids=[]
    )
    return ClassifierTree(
        tree_id="t1",
        nodes={
            "root": root, "task": task, "purpose": purpose,
            "sub_purpose": sub_purpose, "problem": problem, "leaf_root": leaf_root,
        },
        root_ids=["root"],
    )


def _service_with(tree: ClassifierTree) -> ClassifierTreeService:
    repo = ClassifierTreeRepository()
    service = ClassifierTreeService(repo)
    service.import_tree(tree, make_active=True)
    return service


class _ScriptedGateway:
    """Возвращает decisions по очереди — по одной на каждый уровень дерева."""

    def __init__(self, decisions: list[dict]):
        self._decisions = list(decisions)
        self.calls: list[dict] = []

    def generate_structured(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        schema = kwargs["schema"]
        payload = self._decisions.pop(0)
        parsed = schema(**payload)
        return StructuredCallResult(
            parsed=parsed,
            call=LLMCallResult(raw_text="{}", model_name="fake", latency_ms=1, attempts=1),
        )


class TestFragmentClassifier:
    def test_walks_multiple_levels_to_a_leaf(self) -> None:
        gateway = _ScriptedGateway(
            [
                {"selected_child_id": "task", "confidence": 0.9, "reason": "r1"},
                {"selected_child_id": "purpose", "confidence": 0.8, "reason": "r2"},
                {"selected_child_id": "sub_purpose", "confidence": 0.7, "reason": "r3"},
            ]
        )
        classifier = FragmentClassifier(
            tree_service=_service_with(_tree()),
            renderer=ClassifierPromptRenderer(),
            llm_gateway=gateway,  # type: ignore[arg-type]
        )
        result = classifier.classify("некий фрагмент текста")
        assert result is not None
        assert [s.node_id for s in result.path] == ["task", "purpose", "sub_purpose"]
        assert result.reached_leaf is True
        assert result.leaf_node_id == "sub_purpose"
        assert result.overall_confidence == 0.7
        assert len(gateway.calls) == 3

    def test_stops_when_llm_returns_null(self) -> None:
        gateway = _ScriptedGateway(
            [{"selected_child_id": None, "confidence": 0.0, "reason": "no match"}]
        )
        classifier = FragmentClassifier(
            tree_service=_service_with(_tree()),
            renderer=ClassifierPromptRenderer(),
            llm_gateway=gateway,  # type: ignore[arg-type]
        )
        result = classifier.classify("не относится ни к чему")
        assert result is not None
        assert result.path == []
        assert result.reached_leaf is False

    def test_stops_below_confidence_threshold(self) -> None:
        gateway = _ScriptedGateway(
            [{"selected_child_id": "task", "confidence": 0.2, "reason": "unsure"}]
        )
        classifier = FragmentClassifier(
            tree_service=_service_with(_tree()),
            renderer=ClassifierPromptRenderer(),
            llm_gateway=gateway,  # type: ignore[arg-type]
            min_confidence=0.5,
        )
        result = classifier.classify("неуверенный фрагмент")
        assert result is not None
        assert result.path == []

    def test_guards_against_hallucinated_child_id(self) -> None:
        gateway = _ScriptedGateway(
            [{"selected_child_id": "does-not-exist", "confidence": 0.9, "reason": "oops"}]
        )
        classifier = FragmentClassifier(
            tree_service=_service_with(_tree()),
            renderer=ClassifierPromptRenderer(),
            llm_gateway=gateway,  # type: ignore[arg-type]
        )
        result = classifier.classify("x")
        assert result is not None
        assert result.path == []
        assert result.reached_leaf is False

    def test_root_child_that_is_itself_a_leaf_stops_immediately(self) -> None:
        gateway = _ScriptedGateway(
            [{"selected_child_id": "leaf_root", "confidence": 0.9, "reason": "r"}]
        )
        classifier = FragmentClassifier(
            tree_service=_service_with(_tree()),
            renderer=ClassifierPromptRenderer(),
            llm_gateway=gateway,  # type: ignore[arg-type]
        )
        result = classifier.classify("x")
        assert result is not None
        assert [s.node_id for s in result.path] == ["leaf_root"]
        assert result.reached_leaf is True
        assert len(gateway.calls) == 1

    def test_resolves_numeric_index_returned_instead_of_id(self) -> None:
        # Слабые модели (напр. llama3.2) иногда путают нумерацию
        # children_block ("1. Задача (id: task)") с самим id и отвечают
        # позицией вместо строки — это наблюдалось живьём на реальном дереве.
        gateway = _ScriptedGateway(
            [
                {"selected_child_id": 1, "confidence": 0.9, "reason": "по номеру"},
                {"selected_child_id": None, "confidence": 0.0, "reason": "stop"},
            ]
        )
        classifier = FragmentClassifier(
            tree_service=_service_with(_tree()),
            renderer=ClassifierPromptRenderer(),
            llm_gateway=gateway,  # type: ignore[arg-type]
        )
        result = classifier.classify("x")
        assert result is not None
        assert [s.node_id for s in result.path] == ["task"]

    def test_out_of_range_numeric_index_stops_like_null(self) -> None:
        gateway = _ScriptedGateway(
            [{"selected_child_id": 99, "confidence": 0.9, "reason": "bad index"}]
        )
        classifier = FragmentClassifier(
            tree_service=_service_with(_tree()),
            renderer=ClassifierPromptRenderer(),
            llm_gateway=gateway,  # type: ignore[arg-type]
        )
        result = classifier.classify("x")
        assert result is not None
        assert result.path == []

    def test_returns_none_without_active_tree(self) -> None:
        empty_service = ClassifierTreeService(ClassifierTreeRepository())
        classifier = FragmentClassifier(
            tree_service=empty_service,
            renderer=ClassifierPromptRenderer(),
            llm_gateway=_ScriptedGateway([]),  # type: ignore[arg-type]
        )
        assert classifier.classify("x") is None
