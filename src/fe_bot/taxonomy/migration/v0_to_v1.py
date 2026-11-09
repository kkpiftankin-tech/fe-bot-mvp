"""Миграция legacy classified data → SETUP-12 ClassificationState.

T-S12-080: ParsedSection.section_type (enum) → ClassificationState
(bitmap + primary_l0_idx + cascading-unknown-at-1).

T-S12-081: RAGCard.front_matter получает taxonomy_path и связанные
поля на основе ClassificationState секции-источника.

Mapping legacy enum → seed L0 bit (на v1.0.0):
    TASK              → bit 0 (task)
    SCHEMA            → bit 1 (schema)
    ANALYTICS         → bit 2 (analytics)
    GLOSSARY          → bit 3 (glossary)
    VALIDATION        → bit 4 (validation_rule)  [legacy → mapped to rule]
    VALIDATION_RULE   → bit 4 (validation_rule)
    QUESTION_TEMPLATE → bit 5 (question_template)
    DOMAIN_PROFILE    → bit 6 (domain_profile)
    OTHER             → unknown_at_level=0 (нет mapping'а)
    UNKNOWN           → unknown_at_level=0

Идемпотентность: если у секции/карточки уже есть
``classification_state`` или ``taxonomy_version_id`` в front_matter —
пропускаем (skip).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from schemas.setup.parsed_section import ParsedSection, SectionType
from schemas.taxonomy.state import (
    ClassificationState,
    bit_offset,
)

from fe_bot.taxonomy.card_metadata import build_taxonomy_front_matter
from fe_bot.taxonomy.registry import TaxonomyRegistry

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Legacy → seed bit mapping (v1.0.0)
# ----------------------------------------------------------------------

# Семантика: legacy enum-значение → (class_slug на seed L0). bit_index
# resolve'ится через registry.find_by_slug. None → UNKNOWN (нет mapping'а).
LEGACY_SECTION_TYPE_TO_L0_SLUG: dict[SectionType, str | None] = {
    SectionType.TASK: "task",
    SectionType.SCHEMA: "schema",
    SectionType.ANALYTICS: "analytics",
    SectionType.GLOSSARY: "glossary",
    SectionType.VALIDATION: "validation_rule",
    SectionType.VALIDATION_RULE: "validation_rule",
    SectionType.QUESTION_TEMPLATE: "question_template",
    SectionType.DOMAIN_PROFILE: "domain_profile",
    SectionType.OTHER: None,
    SectionType.UNKNOWN: None,
}

# Для удобства тестов: pre-resolved bit'ы для seed v1.0.0.
LEGACY_SECTION_TYPE_TO_L0_BIT: dict[SectionType, int | None] = {
    SectionType.TASK: 0,
    SectionType.SCHEMA: 1,
    SectionType.ANALYTICS: 2,
    SectionType.GLOSSARY: 3,
    SectionType.VALIDATION: 4,
    SectionType.VALIDATION_RULE: 4,
    SectionType.QUESTION_TEMPLATE: 5,
    SectionType.DOMAIN_PROFILE: 6,
    SectionType.OTHER: None,
    SectionType.UNKNOWN: None,
}


# ----------------------------------------------------------------------
# Pure functions
# ----------------------------------------------------------------------


def backfill_classification_state(
    section: ParsedSection,
    *,
    registry: TaxonomyRegistry,
) -> ClassificationState:
    """Строит ClassificationState из legacy полей секции.

    Поведение:
    - TASK/SCHEMA/... → L0-бит, primary_l0_idx, unknown_at_level=1
      (т.к. L1/L2 в legacy не было).
    - OTHER/UNKNOWN → unknown_at_level=0, bitmap=0.
    - confidence_per_level[0] копируется из section.confidence.
    - confidence_per_bit задаётся только для L0.
    - classification_method = "seeded_migration".
    """
    version_id = registry.get_active_version_id()
    slug = LEGACY_SECTION_TYPE_TO_L0_SLUG.get(section.section_type)
    if slug is None:
        return ClassificationState(
            taxonomy_version_id=version_id,
            classification_bitmap=0,
            primary_l0_idx=None,
            primary_l1_idx=None,
            unknown_at_level=0,
            confidence_per_level=(0.0, 0.0, 0.0),
            confidence_per_bit={},
            classification_method="seeded_migration_unknown",
        )
    entry = registry.find_by_slug(
        version_id=version_id, level=0, parent_path="", class_slug=slug
    )
    if entry is None:
        logger.warning(
            "Backfill: seed slug %r not found in registry version %s; "
            "falling back to UNKNOWN",
            slug,
            version_id,
        )
        return ClassificationState(
            taxonomy_version_id=version_id,
            unknown_at_level=0,
            confidence_per_level=(0.0, 0.0, 0.0),
            classification_method="seeded_migration_unknown",
        )
    bitmap = 1 << bit_offset(0, entry.bit_index)
    conf = float(section.confidence)
    return ClassificationState(
        taxonomy_version_id=version_id,
        classification_bitmap=bitmap,
        primary_l0_idx=entry.bit_index,
        primary_l1_idx=None,
        unknown_at_level=1,
        confidence_per_level=(conf, 0.0, 0.0),
        confidence_per_bit={f"0:{entry.bit_index}": conf},
        classification_method="seeded_migration",
    )


def backfill_section(
    section: ParsedSection,
    *,
    registry: TaxonomyRegistry,
) -> ParsedSection:
    """Возвращает копию секции с заполненным ``classification_state``.

    Идемпотентность: если ``section.classification_state is not None``,
    возвращает секцию без изменений.
    """
    if section.classification_state is not None:
        return section
    state = backfill_classification_state(section, registry=registry)
    return section.model_copy(update={"classification_state": state})


def backfill_front_matter(
    section: ParsedSection,
    front_matter: dict[str, Any],
    *,
    registry: TaxonomyRegistry,
) -> dict[str, Any]:
    """Возвращает обновлённый front_matter с taxonomy_* полями.

    Идемпотентность: если в front_matter уже есть
    ``taxonomy_version_id``, возвращает as-is.
    """
    if "taxonomy_version_id" in front_matter:
        return dict(front_matter)
    # Требуется classification_state на секции — если его нет, backfill
    # делает его inline.
    enriched = section if section.classification_state else backfill_section(
        section, registry=registry
    )
    fm_additions = build_taxonomy_front_matter(enriched, registry=registry)
    if not fm_additions:
        return dict(front_matter)
    result = dict(front_matter)
    result.update(fm_additions)
    return result


# ----------------------------------------------------------------------
# Batch migration
# ----------------------------------------------------------------------


@dataclass(slots=True)
class BackfillReport:
    """Итог batch-миграции."""

    total: int = 0
    migrated: int = 0
    skipped: int = 0
    unknown: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors


class _SectionRepoLike(Protocol):
    """Минимальный интерфейс для миграции (subset существующих repo)."""

    def list_all(self) -> list[ParsedSection]: ...
    def upsert(self, section: ParsedSection) -> None: ...


class _CardLike(Protocol):
    doc_id: str
    source_section_ids: list[str]
    front_matter: dict[str, Any]


def migrate_sections(
    section_repo: _SectionRepoLike,
    *,
    registry: TaxonomyRegistry,
    dry_run: bool = True,
) -> BackfillReport:
    """Прогоняет все секции через backfill_section + upsert обратно
    в repository (если не dry_run).

    Idempotent: повторный запуск не меняет уже-мигрированные секции.
    """
    report = BackfillReport()
    sections = list(section_repo.list_all())
    report.total = len(sections)
    for section in sections:
        try:
            if section.classification_state is not None:
                report.skipped += 1
                continue
            updated = backfill_section(section, registry=registry)
            assert updated.classification_state is not None
            if updated.classification_state.unknown_at_level == 0:
                report.unknown += 1
            if not dry_run:
                section_repo.upsert(updated)
            report.migrated += 1
        except Exception as exc:  # noqa: BLE001 — миграция логирует и
            # продолжает, чтобы один битый row не остановил весь run.
            logger.exception(
                "Backfill section %s failed: %s",
                getattr(section, "section_id", "?"),
                exc,
            )
            report.errors.append(
                f"section={getattr(section, 'section_id', '?')}: {exc}"
            )
    return report


def migrate_cards(
    cards: list[_CardLike],
    *,
    sections_by_id: dict[str, ParsedSection],
    registry: TaxonomyRegistry,
    dry_run: bool = True,
) -> BackfillReport:
    """Обогащает RAGCard.front_matter полями taxonomy_*.

    Полагается на словарь ``sections_by_id`` (section_id → ParsedSection)
    для resolve'а primary-секции. Если секция найдена, использует её
    ``classification_state``; иначе делает inline backfill.

    Не меняет card.front_matter напрямую — для in-memory тестов
    мутирует переданный экземпляр. Реальная persistence через
    репозиторий — отдельный шаг (вне scope этого helper'а).
    """
    report = BackfillReport()
    report.total = len(cards)
    for card in cards:
        try:
            if "taxonomy_version_id" in card.front_matter:
                report.skipped += 1
                continue
            primary_section_id = (
                card.source_section_ids[0]
                if card.source_section_ids
                else None
            )
            if primary_section_id is None or primary_section_id not in sections_by_id:
                logger.warning(
                    "Backfill card %s: source section %r not found",
                    card.doc_id,
                    primary_section_id,
                )
                report.unknown += 1
                continue
            section = sections_by_id[primary_section_id]
            updated_fm = backfill_front_matter(
                section, card.front_matter, registry=registry
            )
            if updated_fm.keys() == card.front_matter.keys():
                # build_taxonomy_front_matter вернул {} — нечего добавлять.
                report.unknown += 1
                continue
            if not dry_run:
                card.front_matter = updated_fm  # mutate in place
            report.migrated += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Backfill card %s failed: %s",
                getattr(card, "doc_id", "?"),
                exc,
            )
            report.errors.append(
                f"card={getattr(card, 'doc_id', '?')}: {exc}"
            )
    return report
