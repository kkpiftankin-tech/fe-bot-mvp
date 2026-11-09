"""TaxonomyDocTypeDetector (SETUP-12 / T-S12-050).

DocType detector, использующий иерархическую таксономию вместо
legacy ``_DIRECT_MAPPING``. Читает ``classification_state.primary_l0_slug``
из ``ParsedSection`` и берёт ``doc_type_hint`` из bit-registry.

Fallback: если у секции нет ``classification_state`` (rule-based mode
или legacy данные), делегирует на legacy ``DocTypeDetector``.

Также Fallback: если primary L0-класс не имеет ``doc_type_hint`` (новый
auto-created класс на bit 9 без явного hint'а), идём в legacy detector
как safety net.

См. ADR-HTC-05 (decode bitmap'а через registry).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from schemas.setup.parsed_section import ParsedSection

from fe_bot.setup.rag_card_generation.doc_type_detector import (
    DocTypeDecision,
    DocTypeDetector,
)
from fe_bot.taxonomy.registry import TaxonomyRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TaxonomyDocTypeDetector:
    """Composes TaxonomyRegistry + legacy DocTypeDetector.

    Поведение:
    1. Если ``section.classification_state`` задан И ``primary_l0_idx``
       определён, читаем slug + doc_type_hint из registry.
    2. Если hint задан → возвращаем его (confidence 0.95, reason="taxonomy_hint").
    3. Если classification_state.unknown_at_level=0 (LLM не смог
       классифицировать вообще) → fallback на legacy detector.
    4. Если hint отсутствует у primary L0-класса → fallback на legacy.
    5. Если classification_state=None → fallback на legacy (rule-based).
    """

    registry: TaxonomyRegistry
    legacy: DocTypeDetector

    def detect(self, section: ParsedSection) -> DocTypeDecision:
        state = section.classification_state
        if state is not None and state.primary_l0_idx is not None:
            try:
                entry = self.registry.get_by_bit(
                    version_id=state.taxonomy_version_id,
                    level=0,
                    parent_path="",
                    bit_index=state.primary_l0_idx,
                )
            except LookupError:
                logger.warning(
                    "TaxonomyDocTypeDetector: primary_l0_idx=%d not in "
                    "registry version=%s; falling back to legacy",
                    state.primary_l0_idx,
                    state.taxonomy_version_id,
                )
                return self.legacy.detect(section)
            if entry.doc_type_hint:
                return DocTypeDecision(
                    doc_type=entry.doc_type_hint,
                    confidence=0.95,
                    reason="taxonomy_hint",
                )
            logger.info(
                "TaxonomyDocTypeDetector: primary L0 %r has no doc_type_hint; "
                "falling back to legacy detector",
                entry.class_slug,
            )
        return self.legacy.detect(section)
