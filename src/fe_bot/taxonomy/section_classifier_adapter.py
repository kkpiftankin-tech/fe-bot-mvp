"""HierarchicalSectionClassifier (SETUP-12 / T-S12-041).

Адаптер, оборачивающий ``HierarchicalClassifier`` под интерфейс
``SectionClassifier.apply_to_sections(list[ParsedSection]) ->
list[ParsedSection]``.

Это позволяет вкрутить иерархическую классификацию в существующий
``DocumentParserOrchestrator`` без изменения его API.

Адаптер также делает derive legacy полей ``section_type`` и
``confidence`` из ``classification_state.primary_l0_slug``, чтобы
downstream-код, читающий старые поля, продолжал работать.

Cascading-unknown handling:
- ``unknown_at_level=0`` → ``section_type=UNKNOWN``, status=LOW_CONFIDENCE.
- ``unknown_at_level>=1`` → derive из primary_l0_slug, как обычно.
- None (полная классификация) → derive из primary_l0_slug.
"""

from __future__ import annotations

import logging
from typing import Protocol

from schemas.setup.parsed_section import (
    ParsedSection,
    ParsedSectionStatus,
    SectionType,
)

from fe_bot.taxonomy.hierarchical_classifier import HierarchicalClassifier
from fe_bot.taxonomy.llm_classifier import LLMClassifierError
from fe_bot.taxonomy.registry import TaxonomyRegistry

logger = logging.getLogger(__name__)


# Map L0 slug → legacy SectionType. Покрывает все 9 seed-классов;
# auto-allocated новые L0-классы (на bit 9) → SectionType.UNKNOWN.
_LEGACY_SECTION_TYPE_MAP: dict[str, SectionType] = {
    "task": SectionType.TASK,
    "schema": SectionType.SCHEMA,
    "analytics": SectionType.ANALYTICS,
    "glossary": SectionType.GLOSSARY,
    "validation_rule": SectionType.VALIDATION_RULE,
    "question_template": SectionType.QUESTION_TEMPLATE,
    "domain_profile": SectionType.DOMAIN_PROFILE,
    # process / reference не имеют legacy-аналога; остаются OTHER.
}


class SectionClassifierProtocol(Protocol):
    """Common interface для rule-based и LLM-classifier'ов."""

    def apply_to_sections(
        self, sections: list[ParsedSection]
    ) -> list[ParsedSection]: ...


class HierarchicalSectionClassifier:
    """Wraps HierarchicalClassifier в SectionClassifier-совместимый API.

    Поведение:
    - На каждую секцию вызывает ``HierarchicalClassifier.classify``.
    - Записывает результат в новое поле ``classification_state``.
    - Derive'ит legacy ``section_type`` и ``confidence`` (с уровня 0).
    - Устанавливает ``section_status`` по правилу
      ``LOW_CONFIDENCE`` если ``confidence < threshold``.
    - Метод ``classification_method`` помечает «llm».
    - При ``LLMClassifierError`` (LLM down) пробрасывает исключение —
      orchestrator решает что делать (skip section vs fail parse-job).
    """

    def __init__(
        self,
        *,
        classifier: HierarchicalClassifier,
        registry: TaxonomyRegistry,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._classifier = classifier
        self._registry = registry
        self._threshold = confidence_threshold

    def apply_to_sections(
        self, sections: list[ParsedSection]
    ) -> list[ParsedSection]:
        out: list[ParsedSection] = []
        for section in sections:
            out.append(self._classify_one(section))
        return out

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify_one(self, section: ParsedSection) -> ParsedSection:
        text = section.normalized_text or section.raw_text
        try:
            result = self._classifier.classify(
                section_id=section.section_id,
                section_text=text,
            )
        except LLMClassifierError:
            # LLM unrecoverable error → пробрасываем выше, чтобы
            # orchestrator пометил parse-job соответственно.
            raise

        state = result.state
        legacy_section_type = self._derive_section_type(state)
        legacy_confidence = self._derive_confidence(state)
        section_status = (
            ParsedSectionStatus.LOW_CONFIDENCE
            if legacy_confidence < self._threshold
            else ParsedSectionStatus.CLASSIFIED
        )
        return section.model_copy(
            update={
                "section_type": legacy_section_type,
                "confidence": legacy_confidence,
                "section_status": section_status,
                "classification_method": "llm",
                "classification_state": state,
            }
        )

    def _derive_section_type(self, state) -> SectionType:  # noqa: ANN001 — local helper
        if state.unknown_at_level == 0:
            return SectionType.UNKNOWN
        if state.primary_l0_idx is None:
            return SectionType.UNKNOWN
        entry = self._registry.get_by_bit(
            version_id=state.taxonomy_version_id,
            level=0,
            parent_path="",
            bit_index=state.primary_l0_idx,
        )
        return _LEGACY_SECTION_TYPE_MAP.get(entry.class_slug, SectionType.OTHER)

    @staticmethod
    def _derive_confidence(state) -> float:  # noqa: ANN001 — local helper
        # Берём overall_confidence уровня 0. Если unknown_at_level=0 — 0.0.
        if state.unknown_at_level == 0:
            return 0.0
        return float(state.confidence_per_level[0])
