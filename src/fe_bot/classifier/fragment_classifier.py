"""FragmentClassifier — многоуровневая классификация фрагмента текста по
дереву классификаторов (SETUP-13 / ADR-HTC-09).

На каждом нелистовом узле рендерит промпт (``ClassifierPromptRenderer``)
с реальным ``fragment_text`` и просит маленькую LLM выбрать ОДИН
дочерний класс — при условии, что родительский класс уже определён
предыдущим вызовом (ровно то, что просил пользователь при постановке
задачи SETUP-13). Останавливается на: листе дерева, LLM вернула
``selected_child_id: null``, confidence ниже порога, или LLM
"галлюцинировала" id вне списка реальных детей узла (guard).
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from schemas.classifier.classification_result import (
    ClassifierPathStep,
    FragmentClassificationResult,
)
from schemas.common.defaults import DEFAULT_CLASSIFIER_MODEL

from fe_bot.classifier.prompt_renderer import ClassifierPromptRenderer
from fe_bot.classifier.tree_repository import NoActiveTreeError
from fe_bot.classifier.tree_service import ClassifierTreeService
from fe_bot.llm_gateway.client import LLMGateway

# DEFAULT_CLASSIFIER_MODEL (schemas/common/defaults.py) — почему это НЕ
# DEFAULT_LLM_MODEL ("llama3.2", используется остальными узкими LLM-
# задачами проекта): llama3.2 на живых фрагментах систематически не
# различал содержание, см. docstring константы и ADR-HTC-09.
_DEFAULT_MODEL = DEFAULT_CLASSIFIER_MODEL
_DEFAULT_MIN_CONFIDENCE = 0.5
# Реальное дерево (seed/classifier/asu_v1.txt) — 6 уровней; запас на случай
# более глубоких деревьев в будущем, но не бесконечный цикл при багах.
_DEFAULT_MAX_LEVELS = 10


class _ClassifyDecision(BaseModel):
    # Порядок полей соответствует порядку в JSON-примере промпта
    # (reason → confidence → selected_child_id) — маленькие модели
    # генерируют reason ДО id, только когда это порядок и в примере,
    # иначе reason оказывается пост-хок рационализацией уже выбранного
    # (и иногда даже не совпадает по смыслу с id).
    reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    # str ожидается по контракту промпта ("id из списка выше"), но
    # маленькие модели (напр. llama3.2) регулярно путают нумерацию
    # списка ("1. Имя (id: slug)") с самим id и отвечают позицией —
    # int тоже принимаем и разрешаем в classify() ниже, а не отбрасываем
    # как невалидный ответ (лишний retry ничего не чинит: модель
    # стабильно путается на одном и том же промпте).
    selected_child_id: str | int | None = None


class FragmentClassifier:
    def __init__(
        self,
        *,
        tree_service: ClassifierTreeService,
        renderer: ClassifierPromptRenderer,
        llm_gateway: LLMGateway,
        model: str = _DEFAULT_MODEL,
        min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
        max_levels: int = _DEFAULT_MAX_LEVELS,
    ) -> None:
        self._tree_service = tree_service
        self._renderer = renderer
        self._gateway = llm_gateway
        self._model = model
        self._min_confidence = min_confidence
        self._max_levels = max_levels

    def classify(self, fragment_text: str) -> FragmentClassificationResult | None:
        """Может бросить LLMUnavailableError / InvalidLLMOutputError — caller решает.

        Возвращает None только если нет активного дерева классификаторов
        (библиотека не инициализирована) — это конфигурационная проблема,
        не ошибка конкретного фрагмента.
        """
        try:
            tree = self._tree_service.get_active_tree()
        except NoActiveTreeError:
            return None
        if not tree.root_ids:
            return None

        current_id = tree.root_ids[0]
        path: list[ClassifierPathStep] = []

        for _ in range(self._max_levels):
            node = tree.nodes[current_id]
            if node.is_leaf:
                break

            prompt = self._renderer.render(tree, current_id, fragment_text=fragment_text)
            result = self._gateway.generate_structured(
                prompt=prompt,
                schema=_ClassifyDecision,
                model=self._model,
                temperature=0.0,
            )
            decision = result.parsed
            selected_id = self._resolve_selected_id(decision.selected_child_id, node.children_ids)
            if (
                selected_id is None
                or decision.confidence < self._min_confidence
                or selected_id not in node.children_ids
            ):
                break

            chosen = tree.nodes[selected_id]
            path.append(
                ClassifierPathStep(
                    node_id=chosen.node_id,
                    name=chosen.name,
                    confidence=decision.confidence,
                    reason=decision.reason,
                )
            )
            current_id = chosen.node_id

        reached_leaf = tree.nodes[current_id].is_leaf
        return FragmentClassificationResult(
            tree_id=tree.tree_id, path=path, reached_leaf=reached_leaf
        )

    @staticmethod
    def _resolve_selected_id(
        selected: str | int | None, children_ids: list[str]
    ) -> str | None:
        """int → 1-based позиция в children_block ("1. Имя (id: ...)")."""
        if isinstance(selected, int):
            idx = selected - 1
            return children_ids[idx] if 0 <= idx < len(children_ids) else None
        return selected
