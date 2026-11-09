"""Утилиты для интеграции таксономии в RAG card generation
(SETUP-12 / T-S12-051, T-S12-052).

Содержит две группы helper'ов:

1. ``build_taxonomy_section_dict`` — расширяет ``PromptContext.section``
   с полями ``taxonomy_path``, ``primary_l0`` и т.п., чтобы LLM-prompt
   видел иерархическую классификацию.

2. ``build_taxonomy_front_matter`` — собирает блок полей для
   ``RAGCardMetadataDTO.front_matter``:
   - ``taxonomy_node_id`` (slug primary L0)
   - ``taxonomy_path`` (list[str] от L0 до depth_reached)
   - ``taxonomy_version_id``
   - ``classification_bitmap`` (int, для retrieval-фильтров)
   - ``primary_l0``, ``primary_l1`` (slugs)
   - ``unknown_at_level`` (если != None)

Эти helper'ы — pure functions, не имеют побочных эффектов. Вызываются
из RAG-card orchestrator'а (вне зависимости от того, был ли запущен
LLM-classifier в parser-pipeline'е); если у секции
``classification_state=None``, возвращают пустые / fallback структуры,
что сохраняет backward-compat.
"""

from __future__ import annotations

import logging
from typing import Any

from schemas.setup.parsed_section import ParsedSection
from schemas.taxonomy.state import ClassificationState

from fe_bot.taxonomy.registry import TaxonomyRegistry

logger = logging.getLogger(__name__)


def build_taxonomy_front_matter(
    section: ParsedSection,
    *,
    registry: TaxonomyRegistry,
) -> dict[str, Any]:
    """Возвращает блок front_matter с таксономическими полями.

    Если у секции нет ``classification_state`` — возвращает ``{}``
    (downstream код просто не получит дополнительных полей).

    Если ``classification_state.unknown_at_level=0`` — возвращает
    fallback minimal-блок с ``taxonomy_version_id`` и
    ``classification_bitmap=0``, но без path / node_id (классификация
    не состоялась).
    """
    state = section.classification_state
    if state is None:
        return {}

    fm: dict[str, Any] = {
        "taxonomy_version_id": state.taxonomy_version_id,
        "classification_bitmap": state.classification_bitmap,
    }

    if state.unknown_at_level == 0:
        # Полный cascading-stop: только flag, без path.
        fm["unknown_at_level"] = 0
        return fm

    path = _resolve_taxonomy_path(state, registry)
    if path:
        fm["taxonomy_path"] = path
        fm["taxonomy_node_id"] = path[0]
        fm["primary_l0"] = path[0]
        if len(path) >= 2:
            fm["primary_l1"] = path[1]
    if state.unknown_at_level is not None:
        fm["unknown_at_level"] = state.unknown_at_level
    return fm


def build_taxonomy_section_dict(
    section: ParsedSection,
    *,
    registry: TaxonomyRegistry,
) -> dict[str, Any]:
    """Возвращает поля для ``PromptContext.section`` в формате plain dict.

    Если ``classification_state`` нет, возвращает ``{}`` — orchestrator
    использует только legacy section_type.
    """
    state = section.classification_state
    if state is None or state.unknown_at_level == 0:
        return {}
    path = _resolve_taxonomy_path(state, registry)
    out: dict[str, Any] = {
        "taxonomy_version": state.taxonomy_version_id,
    }
    if path:
        out["taxonomy_path"] = path
        out["primary_l0"] = path[0]
        if len(path) >= 2:
            out["primary_l1"] = path[1]
        if len(path) >= 3:
            out["primary_l2"] = path[2]
    if state.unknown_at_level is not None:
        out["unknown_at_level"] = state.unknown_at_level
    return out


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------


def _resolve_taxonomy_path(
    state: ClassificationState,
    registry: TaxonomyRegistry,
) -> list[str]:
    """Возвращает path как список slug'ов primary классов от L0 до
    depth_reached. Пустой, если primary_l0 не определён.

    На L2 берётся первый установленный бит (primary_l2 не выделяется
    в схеме; обычно их и так 0..1).
    """
    if state.primary_l0_idx is None:
        return []
    try:
        l0_entry = registry.get_by_bit(
            version_id=state.taxonomy_version_id,
            level=0,
            parent_path="",
            bit_index=state.primary_l0_idx,
        )
    except LookupError:
        logger.warning(
            "Taxonomy front_matter: primary_l0_idx=%d not found in registry "
            "version=%s",
            state.primary_l0_idx,
            state.taxonomy_version_id,
        )
        return []
    path = [l0_entry.class_slug]
    if state.primary_l1_idx is None:
        return path
    try:
        l1_entry = registry.get_by_bit(
            version_id=state.taxonomy_version_id,
            level=1,
            parent_path=l0_entry.class_slug,
            bit_index=state.primary_l1_idx,
        )
    except LookupError:
        return path
    path.append(l1_entry.class_slug)
    # L2 — берём первый установленный бит, если есть.
    l2_bits = state.bits_at(2)
    if not l2_bits:
        return path
    l2_parent = f"{l0_entry.class_slug}.{l1_entry.class_slug}"
    try:
        l2_entry = registry.get_by_bit(
            version_id=state.taxonomy_version_id,
            level=2,
            parent_path=l2_parent,
            bit_index=l2_bits[0],
        )
    except LookupError:
        return path
    path.append(l2_entry.class_slug)
    return path


__all__ = [
    "build_taxonomy_front_matter",
    "build_taxonomy_section_dict",
]
