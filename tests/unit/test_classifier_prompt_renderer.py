"""Unit-тесты ClassifierPromptRenderer (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import pytest
from schemas.classifier.node import ClassifierNode
from schemas.classifier.tree import ClassifierTree

from fe_bot.classifier.prompt_renderer import (
    ClassifierPromptRenderer,
    NodeHasNoChildrenError,
)

pytestmark = pytest.mark.unit


def _tree() -> ClassifierTree:
    root = ClassifierNode(
        node_id="root", parent_id=None, level=-1, name="АСУ", children_ids=["task"]
    )
    task = ClassifierNode(
        node_id="task",
        parent_id="root",
        level=0,
        name="Задача",
        children_ids=["purpose", "problem"],
    )
    purpose = ClassifierNode(
        node_id="purpose",
        parent_id="task",
        level=1,
        name="Назначение",
        description="Цель и контекст задачи",
        children_ids=[],
    )
    problem = ClassifierNode(
        node_id="problem", parent_id="task", level=1, name="Проблематика", children_ids=[]
    )
    return ClassifierTree(
        tree_id="t1",
        nodes={"root": root, "task": task, "purpose": purpose, "problem": problem},
        root_ids=["root"],
    )


class TestRender:
    def test_render_includes_node_name_and_children(self) -> None:
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task")
        assert "Задача" in prompt
        # Имя — первично (человекочитаемо), id — вторично, в скобках.
        assert "Назначение (id: purpose)" in prompt
        assert "Проблематика (id: problem)" in prompt

    def test_render_includes_description_when_present(self) -> None:
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task")
        assert "Цель и контекст задачи" in prompt

    def test_render_omits_fragment_section_when_no_fragment_given(self) -> None:
        # Без реального fragment_text (напр., редактирование промпта в
        # библиотеке классификаторов) секция с фрагментом вообще не
        # показывается — это техническая обвязка реального вызова
        # классификации, не то, что редактирует человек.
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task")
        assert "BEGIN_FRAGMENT" not in prompt
        assert "{fragment_text}" not in prompt
        assert "{fragment_section}" not in prompt

    def test_render_embeds_real_fragment_text(self) -> None:
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task", fragment_text="Цель управления объектом.")
        assert "Цель управления объектом." in prompt
        assert "BEGIN_FRAGMENT" in prompt

    def test_leaf_node_raises(self) -> None:
        renderer = ClassifierPromptRenderer()
        with pytest.raises(NodeHasNoChildrenError):
            renderer.render(_tree(), "purpose")

    def test_prompt_override_replaces_template(self) -> None:
        tree = _tree()
        tree.nodes["task"] = tree.nodes["task"].model_copy(
            update={"prompt_override": "CUSTOM PROMPT TEXT"}
        )
        renderer = ClassifierPromptRenderer()
        assert renderer.render(tree, "task") == "CUSTOM PROMPT TEXT"

    def test_prompt_override_still_substitutes_fragment_text(self) -> None:
        # Override — это просто редактируемый текст промпта, а не отдельный
        # шаблон; но {fragment_text} в нём должен по-прежнему подставляться
        # реальным фрагментом на момент классификации.
        tree = _tree()
        tree.nodes["task"] = tree.nodes["task"].model_copy(
            update={"prompt_override": "Custom prompt. Fragment: {fragment_text}"}
        )
        renderer = ClassifierPromptRenderer()
        assert (
            renderer.render(tree, "task", fragment_text="реальный текст")
            == "Custom prompt. Fragment: реальный текст"
        )

    def test_root_path_shown_for_deeper_nodes(self) -> None:
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task")
        assert "путь: АСУ → Задача" in prompt

    def test_own_description_included_when_present(self) -> None:
        # Класс "DNN" и подобные аббревиатуры непонятны без пояснения —
        # description самого классифицируемого узла (не только детей)
        # должен попадать в промпт.
        tree = _tree()
        tree.nodes["task"] = tree.nodes["task"].model_copy(
            update={"description": "Формулировка проблемы, требующей решения"}
        )
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(tree, "task")
        assert "Формулировка проблемы, требующей решения" in prompt

    def test_no_description_leaves_no_dangling_dash(self) -> None:
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task")
        assert "«Задача» (путь: АСУ → Задача)." in prompt
        assert " — ." not in prompt

    def test_children_ids_repeated_before_json_for_small_model_recency(self) -> None:
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task")
        assert "purpose, problem" in prompt

    def test_json_example_asks_for_reason_before_selected_child_id(self) -> None:
        # Маленькие модели на практике выбирают id ДО того, как
        # сформулировать reason, если пример в промпте просит id первым —
        # тогда reason превращается в пост-хок рационализацию, иногда даже
        # не совпадающую по смыслу с выбранным id. Порядок полей в примере
        # JSON должен быть reason → confidence → selected_child_id.
        renderer = ClassifierPromptRenderer()
        prompt = renderer.render(_tree(), "task")
        json_example = prompt[prompt.index("Верни СТРОГО валидный JSON") :]
        reason_pos = json_example.index('"reason"')
        confidence_pos = json_example.index('"confidence"')
        selected_pos = json_example.index('"selected_child_id"')
        assert reason_pos < confidence_pos < selected_pos
