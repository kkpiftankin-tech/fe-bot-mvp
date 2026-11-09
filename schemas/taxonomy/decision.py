"""Decision ADT — результат одного LLM-вызова уровня классификации.

LLM возвращает один из трёх вариантов:
- EXISTING: применил один или несколько существующих классов.
- NEW: предложил новый класс (с описанием); auto-allocator на основе
  similarity-gate решает, переиспользовать ли существующий бит или
  создать новый.
- UNKNOWN: классификация на этом уровне невозможна. Cascading:
  unknown на L_k запрещает drill в L_{k+1}.

Контракт: docs/07-contracts/LLM-CLS-01-classify-at-level.md.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DecisionKind(StrEnum):
    """Тип решения LLM на одном уровне классификации."""

    EXISTING = "existing"
    NEW = "new"
    UNKNOWN = "unknown"


class ExistingSelection(BaseModel):
    """Один выбранный существующий бит."""

    model_config = ConfigDict(extra="forbid")

    bit: int = Field(
        ...,
        ge=0,
        le=9,
        description="Индекс бита в зоне уровня (0..9).",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Уверенность LLM в применимости этого класса.",
    )
    reason: str = Field(
        default="",
        max_length=512,
        description="Короткое обоснование LLM (для аудита).",
    )


class NewClassProposal(BaseModel):
    """Предложение нового класса от LLM (только для DecisionKind.NEW).

    Используется auto-allocator'ом: вычисляется embedding(name + " " +
    description), затем similarity-gate определяет, переиспользовать
    ли существующий бит или зарегистрировать новый класс под parent_path.
    """

    model_config = ConfigDict(extra="forbid")

    name_slug: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="kebab-case-английский идентификатор. Stable, "
        "не меняется после создания.",
    )
    display_name_ru: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Отображаемое имя на русском.",
    )
    display_name_en: str = Field(
        default="",
        max_length=128,
        description="Отображаемое имя на английском (optional).",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=1024,
        description="Описание класса: 1-2 предложения, почему именно "
        "такой класс предложен. Используется для embedding'а в "
        "similarity-gate.",
    )


class Decision(BaseModel):
    """Корневой LLM-вывод одного уровня классификации.

    Инвариант:
    - kind == EXISTING ⇒ selected непусто, proposal=None.
    - kind == NEW ⇒ selected пусто, proposal задан.
    - kind == UNKNOWN ⇒ selected пусто, proposal=None, reason задан.
    """

    model_config = ConfigDict(extra="forbid")

    kind: DecisionKind = Field(..., description="Тип решения.")
    selected: list[ExistingSelection] = Field(
        default_factory=list,
        description="Выбранные existing-биты (для DecisionKind.EXISTING).",
    )
    proposal: NewClassProposal | None = Field(
        default=None,
        description="Предложение нового класса (для DecisionKind.NEW).",
    )
    overall_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Общая уверенность LLM на этом уровне.",
    )
    reason: str = Field(
        default="",
        max_length=1024,
        description="Текстовое обоснование (обязательно для UNKNOWN).",
    )

    @model_validator(mode="after")
    def _kind_invariants(self) -> Decision:
        if self.kind == DecisionKind.EXISTING:
            if not self.selected:
                raise ValueError(
                    "DecisionKind.EXISTING requires at least one selected bit"
                )
            if self.proposal is not None:
                raise ValueError(
                    "DecisionKind.EXISTING must not carry a proposal"
                )
        elif self.kind == DecisionKind.NEW:
            if self.proposal is None:
                raise ValueError(
                    "DecisionKind.NEW requires a new-class proposal"
                )
            if self.selected:
                raise ValueError(
                    "DecisionKind.NEW must not carry selected existing bits"
                )
        else:  # UNKNOWN
            if self.selected or self.proposal is not None:
                raise ValueError(
                    "DecisionKind.UNKNOWN must not carry selected or proposal"
                )
            if not self.reason:
                raise ValueError(
                    "DecisionKind.UNKNOWN must include a reason"
                )
        return self

    @model_validator(mode="after")
    def _unique_bits(self) -> Decision:
        if self.selected:
            seen = set()
            for sel in self.selected:
                if sel.bit in seen:
                    raise ValueError(
                        f"Duplicate bit {sel.bit} in selected list"
                    )
                seen.add(sel.bit)
        return self
