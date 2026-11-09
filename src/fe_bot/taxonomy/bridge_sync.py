"""SectionClassTagsBridge (SETUP-12 / T-S12-042).

Derived-таблица ``section_class_tags`` для глобальных
retrieval-запросов вида «все секции с классом X на уровне Y
независимо от primary L0».

Bitmap — канонический state; bridge — индекс. См. ADR-HTC-07.

Структура (в схеме PG):

    section_class_tags(
      section_id, taxonomy_version, level, parent_path,
      class_slug, is_primary
    )

In-memory реализация для MVP:
- ``materialize_for_section(section_id, state, registry)`` синхронизирует
  записи для одной секции (полная замена tag'ов).
- ``query(level=k, class_slug=...)`` возвращает section_id'ы.

Все записи привязаны к ``taxonomy_version`` — это позволяет корректно
работать с секциями разных версий таксономии.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol

from schemas.taxonomy.state import (
    BITS_PER_LEVEL,
    LEVELS,
    ClassificationState,
)

from fe_bot.taxonomy.registry import TaxonomyRegistry


@dataclass(slots=True, frozen=True)
class SectionClassTag:
    """Одна строка bridge-таблицы."""

    section_id: str
    taxonomy_version: str
    level: int
    parent_path: str
    class_slug: str
    is_primary: bool


class SectionClassTagsRepository(Protocol):
    def replace_for_section(
        self, section_id: str, tags: list[SectionClassTag]
    ) -> None: ...
    def list_for_section(
        self, section_id: str
    ) -> list[SectionClassTag]: ...
    def query(
        self,
        *,
        level: int | None = None,
        class_slug: str | None = None,
        parent_path: str | None = None,
        taxonomy_version: str | None = None,
        is_primary: bool | None = None,
    ) -> list[SectionClassTag]: ...
    def delete_for_section(self, section_id: str) -> None: ...


class InMemorySectionClassTagsRepository:
    """In-memory реализация bridge-репозитория. Thread-safe."""

    def __init__(self) -> None:
        # by section_id для быстрого full-replace.
        self._by_section: dict[str, list[SectionClassTag]] = {}
        self._lock = threading.Lock()

    def replace_for_section(
        self, section_id: str, tags: list[SectionClassTag]
    ) -> None:
        with self._lock:
            # Защита от mismatching section_id внутри tags
            for tag in tags:
                if tag.section_id != section_id:
                    raise ValueError(
                        f"Tag section_id {tag.section_id!r} mismatches "
                        f"argument {section_id!r}"
                    )
            self._by_section[section_id] = list(tags)

    def list_for_section(
        self, section_id: str
    ) -> list[SectionClassTag]:
        with self._lock:
            return list(self._by_section.get(section_id, []))

    def delete_for_section(self, section_id: str) -> None:
        with self._lock:
            self._by_section.pop(section_id, None)

    def query(
        self,
        *,
        level: int | None = None,
        class_slug: str | None = None,
        parent_path: str | None = None,
        taxonomy_version: str | None = None,
        is_primary: bool | None = None,
    ) -> list[SectionClassTag]:
        with self._lock:
            results: list[SectionClassTag] = []
            for tags in self._by_section.values():
                for tag in tags:
                    if level is not None and tag.level != level:
                        continue
                    if class_slug is not None and tag.class_slug != class_slug:
                        continue
                    if (
                        parent_path is not None
                        and tag.parent_path != parent_path
                    ):
                        continue
                    if (
                        taxonomy_version is not None
                        and tag.taxonomy_version != taxonomy_version
                    ):
                        continue
                    if is_primary is not None and tag.is_primary != is_primary:
                        continue
                    results.append(tag)
            return results


class SectionClassTagsBridge:
    """Derives ``SectionClassTag`` записи из ``ClassificationState`` и
    синхронизирует их в репозиторий."""

    def __init__(
        self,
        *,
        registry: TaxonomyRegistry,
        repository: SectionClassTagsRepository | None = None,
    ) -> None:
        self._registry = registry
        self._repo = repository or InMemorySectionClassTagsRepository()

    @property
    def repository(self) -> SectionClassTagsRepository:
        return self._repo

    def materialize_for_section(
        self,
        section_id: str,
        state: ClassificationState,
    ) -> list[SectionClassTag]:
        """Полностью пересоздаёт bridge-записи для одной секции."""
        tags = self._derive_tags(section_id, state)
        self._repo.replace_for_section(section_id, tags)
        return tags

    def delete_for_section(self, section_id: str) -> None:
        self._repo.delete_for_section(section_id)

    # ------------------------------------------------------------------
    # Derivation
    # ------------------------------------------------------------------

    def _derive_tags(
        self,
        section_id: str,
        state: ClassificationState,
    ) -> list[SectionClassTag]:
        tags: list[SectionClassTag] = []
        version = state.taxonomy_version_id
        # Resolve primary slugs lazily (потребуются для parent_path L1/L2).
        primary_l0_slug: str | None = None
        primary_l1_slug: str | None = None

        for level in range(LEVELS):
            bits = state.bits_at(level)
            if not bits:
                continue
            for bit in bits:
                parent_path = self._parent_path_for_level(
                    level,
                    primary_l0_slug=primary_l0_slug,
                    primary_l1_slug=primary_l1_slug,
                )
                if parent_path is None:
                    # Не должны попасть сюда: cascading-инвариант
                    # state-схемы гарантирует, что L1/L2 биты возможны
                    # только при наличии primary L0/L1.
                    continue
                entry = self._registry.get_by_bit(
                    version_id=version,
                    level=level,
                    parent_path=parent_path,
                    bit_index=bit,
                )
                is_primary = self._is_primary(state, level, bit)
                tags.append(
                    SectionClassTag(
                        section_id=section_id,
                        taxonomy_version=version,
                        level=level,
                        parent_path=parent_path,
                        class_slug=entry.class_slug,
                        is_primary=is_primary,
                    )
                )
                if level == 0 and is_primary:
                    primary_l0_slug = entry.class_slug
                if level == 1 and is_primary:
                    primary_l1_slug = entry.class_slug
        return tags

    @staticmethod
    def _parent_path_for_level(
        level: int,
        *,
        primary_l0_slug: str | None,
        primary_l1_slug: str | None,
    ) -> str | None:
        if level == 0:
            return ""
        if level == 1:
            return primary_l0_slug
        if level == 2:
            if primary_l0_slug is None or primary_l1_slug is None:
                return None
            return f"{primary_l0_slug}.{primary_l1_slug}"
        return None

    @staticmethod
    def _is_primary(
        state: ClassificationState, level: int, bit: int
    ) -> bool:
        if level == 0:
            return state.primary_l0_idx == bit
        if level == 1:
            return state.primary_l1_idx == bit
        # На L2 «primary» = единственный установленный бит (если их
        # несколько — primary не выделяется в текущей модели).
        l2_bits = state.bits_at(2)
        return len(l2_bits) == 1 and l2_bits[0] == bit


__all__ = [
    "InMemorySectionClassTagsRepository",
    "SectionClassTag",
    "SectionClassTagsBridge",
    "SectionClassTagsRepository",
    "BITS_PER_LEVEL",
]
