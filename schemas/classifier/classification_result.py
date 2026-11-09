"""FragmentClassificationResult — результат многоуровневой классификации
фрагмента текста по дереву классификаторов (SETUP-13 / ADR-HTC-09).

Заполняется ``fe_bot.classifier.fragment_classifier.FragmentClassifier``:
на каждом нелистовом узле дерева маленькая LLM выбирает один дочерний
класс (или ``null``, если фрагмент явно не подходит) — путь по дереву
от корня до точки остановки и есть результат классификации.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClassifierPathStep(BaseModel):
    """Один уровень классификации: выбранный дочерний класс + confidence."""

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=2000)


class FragmentClassificationResult(BaseModel):
    """Путь по дереву от корня до точки остановки (лист / low-confidence / null)."""

    model_config = ConfigDict(extra="forbid")

    tree_id: str = Field(..., min_length=1)
    path: list[ClassifierPathStep] = Field(default_factory=list)
    reached_leaf: bool = Field(
        default=False,
        description="True если классификация дошла до листового узла дерева.",
    )

    @property
    def leaf_node_id(self) -> str | None:
        return self.path[-1].node_id if self.path else None

    @property
    def path_names(self) -> list[str]:
        return [step.name for step in self.path]

    @property
    def overall_confidence(self) -> float:
        """Минимум по пути — цепочка не увереннее своего самого слабого звена."""
        if not self.path:
            return 0.0
        return min(step.confidence for step in self.path)
