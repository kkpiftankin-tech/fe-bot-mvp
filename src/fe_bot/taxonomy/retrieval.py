"""Taxonomy filters для retrieval (SETUP-12 / T-S12-060, T-S12-061).

Содержит два набора утилит:

1. ``build_payload`` — extension для VectorIndex payload (то, что
   индексируется поверх каждого chunk'а). Включает плоские поля для
   быстрых exact-match фильтров (``primary_l0``, ``primary_l1``,
   ``taxonomy_version``, ``bitmap_l0``, ``bitmap_l1``, ``bitmap_l2``),
   а также ``taxonomy_path`` как list[str].

2. ``TaxonomyFilter`` — типизированный фильтр с поддержкой:
   - exact match по slug (primary_l0, primary_l1)
   - prefix match по taxonomy_path (path_prefix=["task"] → находит
     `task`, `task.pvo`, `task.pvo.tracking`)
   - bit-test (``has_bit_at(level, bit)``) — для multi-tag запросов
     («любая секция, где L0-бит 1 установлен»)
   - taxonomy_version filter

Зачем bitmap при сохранённом ``taxonomy_path``: фильтры по multi-tag
(secondary L0) выражаются только через bitmap, потому что path
содержит только primary chain.

См. ADR-HTC-07.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from schemas.taxonomy.state import (
    BITS_PER_LEVEL,
    LEVELS,
    ClassificationState,
    bit_offset,
    level_mask,
)

from fe_bot.taxonomy.card_metadata import _resolve_taxonomy_path
from fe_bot.taxonomy.registry import TaxonomyRegistry

# ----------------------------------------------------------------------
# Payload extension
# ----------------------------------------------------------------------


def build_payload(
    state: ClassificationState | None,
    *,
    registry: TaxonomyRegistry,
) -> dict[str, Any]:
    """Возвращает payload-блок для VectorIndex с таксономическими полями.

    Если ``state=None`` — возвращает ``{}`` (карточка индексируется
    без таксономических полей; запросы по таксономии её не найдут).
    """
    if state is None:
        return {}
    out: dict[str, Any] = {
        "taxonomy_version": state.taxonomy_version_id,
        "bitmap_l0": state.classification_bitmap & level_mask(0),
        "bitmap_l1": (state.classification_bitmap & level_mask(1)) >> BITS_PER_LEVEL,
        "bitmap_l2": (state.classification_bitmap & level_mask(2)) >> (2 * BITS_PER_LEVEL),
        "classification_bitmap": state.classification_bitmap,
    }
    if state.unknown_at_level is not None:
        out["unknown_at_level"] = state.unknown_at_level

    path = _resolve_taxonomy_path(state, registry)
    if path:
        out["taxonomy_path"] = path
        out["primary_l0"] = path[0]
        if len(path) >= 2:
            out["primary_l1"] = path[1]
        if len(path) >= 3:
            out["primary_l2"] = path[2]
    return out


# ----------------------------------------------------------------------
# TaxonomyFilter
# ----------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class BitTest:
    """Проверка установки конкретного бита (level, bit_in_level)."""

    level: int
    bit_in_level: int


@dataclass(slots=True)
class TaxonomyFilter:
    """Декларативный фильтр на основе таксономии.

    Все поля комбинируются через AND (must match all). Внутри list-полей
    срабатывает первое совпадение (OR).

    Поля:
        primary_l0 — list допустимых slug'ов primary L0 (OR).
        primary_l1 — list допустимых slug'ов primary L1 (OR).
        path_prefix — list[str], проверяет что taxonomy_path начинается
            с указанной последовательности slug'ов
            (e.g. ["task", "pvo"] подходит для path = ["task", "pvo", "tracking"]).
        any_bit — list BitTest, секция должна иметь хотя бы один из
            этих бит установленным (OR). Используется для multi-tag.
        all_bits — list BitTest, секция должна иметь ВСЕ эти биты.
        taxonomy_version — точная версия таксономии.
        max_unknown_level — максимально допустимое значение
            unknown_at_level (например, 2 = принимаем только полностью
            классифицированные + те, что unknown_at_l2). None = принимаем
            всё.
    """

    primary_l0: list[str] = field(default_factory=list)
    primary_l1: list[str] = field(default_factory=list)
    path_prefix: list[str] = field(default_factory=list)
    any_bit: list[BitTest] = field(default_factory=list)
    all_bits: list[BitTest] = field(default_factory=list)
    taxonomy_version: str | None = None
    max_unknown_level: int | None = None

    def matches_payload(self, payload: dict[str, Any]) -> bool:
        """True если payload удовлетворяет всем критериям фильтра."""
        if self.taxonomy_version is not None:
            if payload.get("taxonomy_version") != self.taxonomy_version:
                return False

        if self.max_unknown_level is not None:
            unk = payload.get("unknown_at_level")
            # None значит «полностью классифицировано» — допустимо.
            if unk is not None and unk < self.max_unknown_level:
                return False

        if self.primary_l0:
            if payload.get("primary_l0") not in self.primary_l0:
                return False

        if self.primary_l1:
            if payload.get("primary_l1") not in self.primary_l1:
                return False

        if self.path_prefix:
            path = payload.get("taxonomy_path") or []
            if not _path_starts_with(path, self.path_prefix):
                return False

        if self.any_bit:
            bitmap = payload.get("classification_bitmap", 0)
            if not any(_bit_is_set(bitmap, bt) for bt in self.any_bit):
                return False

        if self.all_bits:
            bitmap = payload.get("classification_bitmap", 0)
            if not all(_bit_is_set(bitmap, bt) for bt in self.all_bits):
                return False

        return True

    def to_payload_dict(self) -> dict[str, Any]:
        """Возвращает подмножество, выразимое через VectorIndex
        exact-match фильтры. Используется для pre-фильтрации.

        Поля с list (primary_l0, primary_l1) кодируются как list —
        VectorIndex поддерживает ``in``. Bitmap/path-prefix критерии
        НЕ выражаются и должны применяться post-фильтром через
        ``matches_payload``.
        """
        out: dict[str, Any] = {}
        if self.taxonomy_version is not None:
            out["taxonomy_version"] = self.taxonomy_version
        if self.primary_l0:
            out["primary_l0"] = list(self.primary_l0)
        if self.primary_l1:
            out["primary_l1"] = list(self.primary_l1)
        return out

    @property
    def has_bitwise_criteria(self) -> bool:
        return bool(
            self.path_prefix or self.any_bit or self.all_bits or self.max_unknown_level is not None
        )


def apply_filter_to_hits(
    hits: list[Any],
    taxonomy_filter: TaxonomyFilter,
) -> list[Any]:
    """Post-filter retrieval hits через ``TaxonomyFilter``.

    Каждый hit должен иметь свойство/поле ``payload`` (dict).
    Возвращает только те hits, у которых ``matches_payload(payload)``.
    """
    return [
        h
        for h in hits
        if taxonomy_filter.matches_payload(getattr(h, "payload", {}))
    ]


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _bit_is_set(bitmap: int, test: BitTest) -> bool:
    if not 0 <= test.level <= LEVELS - 1:
        return False
    if not 0 <= test.bit_in_level <= BITS_PER_LEVEL - 1:
        return False
    return bool(bitmap & (1 << bit_offset(test.level, test.bit_in_level)))


def _path_starts_with(path: list[str], prefix: list[str]) -> bool:
    if len(prefix) > len(path):
        return False
    return all(p == path[i] for i, p in enumerate(prefix))


__all__ = [
    "BitTest",
    "TaxonomyFilter",
    "apply_filter_to_hits",
    "build_payload",
]
