"""ClassifierNode — один узел дерева библиотеки классификаторов.

SETUP-13 / ADR-HTC-09. Глубина и ширина дерева не ограничены схемой
(в отличие от 30-битной bitmap-таксономии SETUP-12) — см.
docs/03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClassifierNode(BaseModel):
    """Узел дерева классификаторов.

    ``is_leaf`` — вычисляемое свойство (``len(children_ids) == 0``),
    не хранится отдельным полем, чтобы не могло разойтись с реальным
    состоянием ``children_ids``.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., min_length=1, max_length=64)
    parent_id: str | None = Field(
        default=None, description="None только для корневых узлов дерева."
    )
    level: int = Field(
        ...,
        ge=-1,
        description=(
            "0 — прямые дети корня дерева (корень сам по себе не "
            "считается уровнем — см. import_tree.py). -1 зарезервирован "
            "за синтетическим корневым узлом дерева."
        ),
    )
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2048)
    children_ids: list[str] = Field(default_factory=list)
    prompt_override: str | None = Field(
        default=None,
        max_length=8192,
        description=(
            "Если задан — используется вместо общего шаблона "
            "prompts/classification/classify_node.txt при рендере "
            "промпта для этого узла."
        ),
    )

    @property
    def is_leaf(self) -> bool:
        return len(self.children_ids) == 0
