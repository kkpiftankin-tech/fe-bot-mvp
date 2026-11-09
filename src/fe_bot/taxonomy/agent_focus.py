"""TaxonomyFocus для runtime-агентов (SETUP-12 / T-S12-062).

Декларация «доменной зоны интереса» агента в терминах таксономии.
Используется для автоматического сужения retrieval-запросов.

Пример:

    class FeatureSynthesisAgent:
        taxonomy_focus = TaxonomyFocus(
            include_paths=["task.*", "schema.*"],
            exclude_paths=[],
        )

    # В rantime: retrieval-сервис применяет focus.to_filter() к запросам.

Wildcards:
- ``"task"`` — точное совпадение primary_l0.
- ``"task.*"`` — все под task (включая task.pvo, task.pvo.tracking).
- ``"task.pvo"`` — точное совпадение path[:2].
- ``"task.pvo.*"`` — все под task.pvo.

Это не runtime-логика самих агентов (TBD в будущих слайсах) —
только спецификация контракта, через которую агенты будут заявлять
свои интересы.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fe_bot.taxonomy.retrieval import TaxonomyFilter


@dataclass(slots=True, frozen=True)
class TaxonomyPathPattern:
    """Распарсенный pattern для taxonomy focus."""

    parts: tuple[str, ...]  # ("task",) или ("task", "pvo")
    is_wildcard: bool  # True если pattern заканчивается на ".*"

    def matches(self, path: list[str]) -> bool:
        if not self.parts:
            return False
        if self.is_wildcard:
            # path должен начинаться с self.parts
            if len(path) < len(self.parts):
                return False
            return all(p == path[i] for i, p in enumerate(self.parts))
        # точное совпадение длины
        if len(path) != len(self.parts):
            return False
        return all(p == path[i] for i, p in enumerate(self.parts))

    @classmethod
    def parse(cls, raw: str) -> TaxonomyPathPattern:
        s = raw.strip()
        if not s:
            raise ValueError("Empty taxonomy pattern")
        is_wildcard = s.endswith(".*")
        if is_wildcard:
            s = s[:-2]
            if not s:
                raise ValueError("Bare '.*' wildcard not allowed; use a prefix")
        parts = tuple(part for part in s.split(".") if part)
        if not parts:
            raise ValueError(f"Invalid taxonomy pattern: {raw!r}")
        return cls(parts=parts, is_wildcard=is_wildcard)


@dataclass(slots=True, frozen=True)
class TaxonomyFocus:
    """Декларация доменного интереса агента.

    Семантика: секция/карточка проходит focus, если:
    - ВКЛЮЧЕНА хотя бы одним include-pattern (или include_paths пусто
      → проходит всё);
    - НЕ ВКЛЮЧЕНА ни одним exclude-pattern.
    """

    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()

    def matches_path(self, taxonomy_path: list[str]) -> bool:
        """True если путь проходит focus."""
        include_patterns = [TaxonomyPathPattern.parse(p) for p in self.include_paths]
        exclude_patterns = [TaxonomyPathPattern.parse(p) for p in self.exclude_paths]
        if include_patterns:
            if not any(p.matches(taxonomy_path) for p in include_patterns):
                return False
        if exclude_patterns:
            if any(p.matches(taxonomy_path) for p in exclude_patterns):
                return False
        return True

    def matches_payload(self, payload: dict[str, Any]) -> bool:
        """True если payload (с полем taxonomy_path) проходит focus."""
        path = payload.get("taxonomy_path") or []
        return self.matches_path(path)

    def to_filter(self) -> TaxonomyFilter:
        """Конвертация include-paths в ``TaxonomyFilter`` (best-effort).

        Простые случаи:
        - один include типа "task" или "task.*" → path_prefix=["task"]
        - один include "task.pvo" → path_prefix=["task", "pvo"]

        Сложные случаи (несколько include / exclude) НЕ конвертируются —
        вызывающий код должен использовать ``matches_payload`` напрямую
        как post-filter.

        Возвращает пустой TaxonomyFilter если include_paths пусто или
        невыразимо.
        """
        if not self.include_paths or self.exclude_paths or len(self.include_paths) > 1:
            return TaxonomyFilter()
        pattern = TaxonomyPathPattern.parse(self.include_paths[0])
        prefix = list(pattern.parts)
        # is_wildcard или нет — оба случая выражаются prefix-фильтром
        return TaxonomyFilter(path_prefix=prefix)


def collect_focuses(*focuses: TaxonomyFocus) -> TaxonomyFocus:
    """Объединяет несколько focus'ов: include = union, exclude = union.

    Полезно при композиции агентов (e.g. multi-step pipeline).
    """
    all_include: tuple[str, ...] = ()
    all_exclude: tuple[str, ...] = ()
    for f in focuses:
        all_include = all_include + f.include_paths
        all_exclude = all_exclude + f.exclude_paths
    return TaxonomyFocus(
        include_paths=all_include,
        exclude_paths=all_exclude,
    )


__all__ = [
    "TaxonomyFocus",
    "TaxonomyPathPattern",
    "collect_focuses",
]
