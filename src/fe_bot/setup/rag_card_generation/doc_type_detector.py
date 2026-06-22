"""DocTypeDetector (SETUP-05 / T-S05-015).

Rule-based маппинг ``ParsedSection.section_type`` (из SETUP-04 classifier) в
target ``doc_type`` для RAG-карточки.

MVP scope — 7 doc_types: schema_card, task_card, analytics_card,
field_definition_card, feature_pattern_card, validation_rule_card,
question_template_card.

Decision rules:
- Прямой mapping section_type → doc_type → confidence=0.9, reason="direct_mapping".
- OTHER/UNKNOWN с keyword "определение|definition" в title → field_definition_card,
  confidence=0.5, reason="fallback_keyword".
- OTHER/UNKNOWN без признаков → INVALID, confidence=0.0, reason="no_signal".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from schemas.setup.parsed_section import ParsedSection, SectionType

_DIRECT_MAPPING: dict[SectionType, str] = {
    SectionType.TASK: "task_card",
    SectionType.SCHEMA: "schema_card",
    SectionType.ANALYTICS: "analytics_card",
    SectionType.GLOSSARY: "field_definition_card",
    SectionType.VALIDATION: "validation_rule_card",
    SectionType.VALIDATION_RULE: "validation_rule_card",
    SectionType.QUESTION_TEMPLATE: "question_template_card",
}

_DEFINITION_PATTERN = re.compile(
    r"\b(определение|definition|definitions|термин|terms|glossary)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DocTypeDecision:
    """Результат detection: target doc_type + confidence + reason."""

    doc_type: str | None
    confidence: float
    reason: str

    @property
    def is_valid(self) -> bool:
        return self.doc_type is not None


class DocTypeDetector:
    """Rule-based detector. Не использует LLM."""

    def detect(self, section: ParsedSection) -> DocTypeDecision:
        # Прямой mapping.
        target = _DIRECT_MAPPING.get(section.section_type)
        if target is not None:
            return DocTypeDecision(
                doc_type=target,
                confidence=0.9,
                reason="direct_mapping",
            )

        # Fallback для OTHER / UNKNOWN / DOMAIN_PROFILE.
        title = section.title or ""
        heading_path_text = " ".join(section.heading_path or [])
        haystack = f"{title} {heading_path_text}"
        if _DEFINITION_PATTERN.search(haystack):
            return DocTypeDecision(
                doc_type="field_definition_card",
                confidence=0.5,
                reason="fallback_keyword",
            )

        return DocTypeDecision(
            doc_type=None,
            confidence=0.0,
            reason="no_signal",
        )
