"""Prompt renderer для классификации (SETUP-12 / T-S12-030).

Загружает ``prompts/classification/classify_at_level.txt`` и рендерит
с context'ом для одного уровня.

Шаблон использует str.format-style placeholders (``{level}``,
``{context_block}`` и т.д.). Условные блоки (L0 vs L1 vs L2)
готовятся renderer'ом в Python и подставляются как pre-formatted
strings — это позволяет обойтись без Jinja2 в зависимостях.

См. контракт: docs/07-contracts/LLM-CLS-01-classify-at-level.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from string import Template

from schemas.taxonomy.registry import (
    MAX_BITS_PER_LEVEL,
    TaxonomyBitRegistryEntry,
)

_DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3]
    / "prompts"
    / "classification"
    / "classify_at_level.txt"
)


class PromptTemplateNotFoundError(LookupError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Classification prompt template not found: {path}")


@dataclass(slots=True)
class ClassificationPromptInput:
    """Параметры рендеринга для одного LLM-вызова.

    ``primary_l0_slug``/``primary_l0_display_ru`` обязательны при
    ``level >= 1``; ``primary_l1_*`` — при ``level == 2``.
    ``also_applies_l0`` — list slug'ов остальных L0-битов (мульти-тег).

    ``candidates`` — текущие активные классы под parent_path; пустой
    список значит «на этом уровне ничего не зарегистрировано, можешь
    свободно предлагать новый».

    ``section_text`` — нормализованный текст секции (обычно
    ``ParsedSection.normalized_text`` или raw_text).
    """

    level: int
    parent_path: str
    candidates: list[TaxonomyBitRegistryEntry]
    section_text: str
    free_slots_count: int

    primary_l0_slug: str | None = None
    primary_l0_display_ru: str | None = None
    primary_l1_slug: str | None = None
    primary_l1_display_ru: str | None = None
    also_applies_l0: list[str] = field(default_factory=list)
    max_classes_per_level: int = MAX_BITS_PER_LEVEL


class ClassificationPromptRenderer:
    """Stateful renderer: грузит шаблон один раз, рендерит N раз.

    Шаблон валидируется лениво — при первом ``render``.
    """

    def __init__(self, template_path: Path | None = None) -> None:
        self._template_path = template_path or _DEFAULT_TEMPLATE_PATH
        self._template_text: str | None = None

    @property
    def template_path(self) -> Path:
        return self._template_path

    def _ensure_loaded(self) -> str:
        if self._template_text is not None:
            return self._template_text
        if not self._template_path.exists():
            raise PromptTemplateNotFoundError(self._template_path)
        text = self._template_path.read_text(encoding="utf-8")
        self._template_text = text
        return text

    def render(self, params: ClassificationPromptInput) -> str:
        """Возвращает готовый prompt-text."""
        _validate_params(params)
        template = self._ensure_loaded()
        substitutions = {
            "level": params.level,
            "context_block": _build_context_block(params),
            "scope_suffix": _build_scope_suffix(params),
            "candidates_count": len(params.candidates),
            "max_classes_per_level": params.max_classes_per_level,
            "candidates_block": _build_candidates_block(params),
            "free_slots_hint": _build_free_slots_hint(params),
            "section_text": params.section_text,
        }
        # Используем str.format с двойными скобками для JSON-блока:
        # шаблон уже содержит {{ }} для литералов JSON.
        return template.format(**substitutions)


# ----------------------------------------------------------------------
# Internal builders
# ----------------------------------------------------------------------


def _validate_params(params: ClassificationPromptInput) -> None:
    if params.level not in (0, 1, 2):
        raise ValueError(f"level must be 0..2, got {params.level}")
    if params.level == 0 and params.parent_path != "":
        raise ValueError("level=0 requires empty parent_path")
    if params.level == 1:
        if not params.parent_path:
            raise ValueError("level=1 requires non-empty parent_path")
        if not params.primary_l0_slug:
            raise ValueError("level=1 requires primary_l0_slug")
    if params.level == 2:
        if "." not in params.parent_path:
            raise ValueError(
                "level=2 parent_path must be '<l0>.<l1>'"
            )
        if not params.primary_l0_slug or not params.primary_l1_slug:
            raise ValueError(
                "level=2 requires primary_l0_slug and primary_l1_slug"
            )
    if not params.section_text.strip():
        raise ValueError("section_text must be non-empty")
    if params.free_slots_count < 0:
        raise ValueError("free_slots_count cannot be negative")


def _build_context_block(params: ClassificationPromptInput) -> str:
    if params.level == 0:
        return ""
    lines = ["", "Контекст вышестоящих уровней:"]
    lines.append(
        f"- L0 (основной класс) = \"{params.primary_l0_slug}\""
        f" ({params.primary_l0_display_ru or params.primary_l0_slug})"
    )
    others = [s for s in params.also_applies_l0 if s != params.primary_l0_slug]
    if others:
        lines.append(
            "- Также применимы (multi-tag L0): "
            + ", ".join(f'"{s}"' for s in others)
        )
    if params.level == 2:
        lines.append(
            f"- L1 (основной подкласс) = \"{params.primary_l1_slug}\""
            f" ({params.primary_l1_display_ru or params.primary_l1_slug})"
        )
    lines.append("")
    return "\n".join(lines)


def _build_scope_suffix(params: ClassificationPromptInput) -> str:
    if params.level == 0:
        return ""
    return f" под \"{params.parent_path}\""


def _build_candidates_block(params: ClassificationPromptInput) -> str:
    if not params.candidates:
        return "  (на этом уровне пока нет ни одного класса — можешь свободно предложить новый через decision=\"new\")"
    sorted_candidates = sorted(params.candidates, key=lambda e: e.bit_index)
    lines: list[str] = []
    for entry in sorted_candidates:
        lines.append(
            f"[{entry.bit_index}] {entry.class_slug} — {entry.display_name_ru}"
        )
        # Каждое описание на отступе для читаемости LLM.
        desc = entry.description.strip().replace("\n", " ")
        lines.append(f"    Описание: {desc}")
    return "\n".join(lines)


def _build_free_slots_hint(params: ClassificationPromptInput) -> str:
    if params.free_slots_count > 0:
        return (
            f"Свободных слотов на этом уровне: {params.free_slots_count}. "
            "Если ни один из существующих классов не подходит, ты МОЖЕШЬ "
            "предложить новый класс (`decision: \"new\"`)."
        )
    return (
        f"Свободных слотов нет (все {params.max_classes_per_level} заняты). "
        "Если ни один не подходит идеально, выбери ближайший по смыслу "
        "из существующих."
    )


def _safe_format(template: str, mapping: dict[str, object]) -> str:
    """str.format-обёртка с понятным сообщением при missing placeholder."""
    try:
        return Template(template).safe_substitute(mapping)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Prompt template render failed: {exc}") from exc
