"""SectionClassifier (SETUP-04 / T-S04-018, rule-based).

Классифицирует ParsedSection в SectionType по keyword'ам.
Confidence:
- 0.9 — keyword'и нашлись в title (точный матч на названии секции)
- 0.7 — keyword'и нашлись только в первых 500 символов текста
- 0.5 — ни одного матча → UNKNOWN

LOW_CONFIDENCE = confidence < 0.7 (configurable).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Final

from schemas.setup.parsed_section import (
    ParsedSection,
    ParsedSectionStatus,
    SectionType,
)
from schemas.setup.section_classification import (
    ClassificationMethod,
    SectionClassification,
)

# Keyword → SectionType маппинг.
# Латиница + кириллица. Все в lower-case.
_KEYWORDS: Final[dict[str, list[str]]] = {
    SectionType.TASK.value: [
        "task",
        "tasks",
        "задач",
        "задача",
        "задачи",
        "feature",
        "признак",
        "признаки",
    ],
    SectionType.SCHEMA.value: [
        "schema",
        "schemas",
        "схем",
        "схема",
        "structure",
        "table",
        "поле",
        "поля",
    ],
    SectionType.ANALYTICS.value: [
        "analytics",
        "analysis",
        "аналитик",
        "аналитика",
        "анализ",
        "метрик",
        "metric",
    ],
    SectionType.GLOSSARY.value: [
        "glossary",
        "глоссарий",
        "термин",
        "терминолог",
        "definition",
        "определение",
    ],
    SectionType.VALIDATION_RULE.value: [
        "validation",
        "validation_rule",
        "валидаци",
        "проверк",
        "rule",
        "правил",
    ],
    SectionType.QUESTION_TEMPLATE.value: [
        "question",
        "вопрос",
        "вопросы",
        "template",
        "шаблон",
        "qa",
    ],
}

# Sentinel: default threshold для low_confidence.
DEFAULT_CONFIDENCE_THRESHOLD = 0.7

_TITLE_CONFIDENCE = 0.9
_TEXT_CONFIDENCE = 0.7
_NO_MATCH_CONFIDENCE = 0.5


class SectionClassifier:
    """Rule-based классификатор секций.

    Не имеет внешних зависимостей. Используется per-section в
    DocumentParserOrchestrator после извлечения секций стратегией.
    """

    def __init__(self, *, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> None:
        self._threshold = confidence_threshold
        # Precompile patterns для каждого keyword.
        self._patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {
            section_type: [
                (kw, re.compile(rf"\b{re.escape(kw)}", re.IGNORECASE)) for kw in keywords
            ]
            for section_type, keywords in _KEYWORDS.items()
        }

    def classify(self, section: ParsedSection) -> SectionClassification:
        title = section.title or ""
        text_snippet = section.raw_text[:500] if section.raw_text else ""

        # Этап 1: поиск в title.
        title_hits = self._find_hits(title)
        if title_hits:
            section_type_str, matched_kw = self._pick_best(title_hits)
            section_type = self._cast_to_section_type(section_type_str)
            return self._build_classification(
                section_id=section.section_id,
                section_type=section_type,
                confidence=_TITLE_CONFIDENCE,
                reason=f"Keyword {matched_kw!r} matched in title",
            )

        # Этап 2: поиск в первых 500 символов raw_text.
        text_hits = self._find_hits(text_snippet)
        if text_hits:
            section_type_str, matched_kw = self._pick_best(text_hits)
            section_type = self._cast_to_section_type(section_type_str)
            return self._build_classification(
                section_id=section.section_id,
                section_type=section_type,
                confidence=_TEXT_CONFIDENCE,
                reason=f"Keyword {matched_kw!r} matched in body",
            )

        # Этап 3: нет матчей → UNKNOWN.
        return self._build_classification(
            section_id=section.section_id,
            section_type=SectionType.UNKNOWN,
            confidence=_NO_MATCH_CONFIDENCE,
            reason="No keyword matches",
        )

    def is_low_confidence(self, classification: SectionClassification) -> bool:
        """Below threshold = low confidence."""
        return classification.confidence < self._threshold

    def apply_to_sections(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        """Обогащает секции результатом классификации.

        Каждая секция получает обновлённый section_type, confidence,
        section_status (LOW_CONFIDENCE если ниже порога) и
        classification_method.
        """
        result: list[ParsedSection] = []
        for section in sections:
            cls = self.classify(section)
            new_status = (
                ParsedSectionStatus.LOW_CONFIDENCE
                if self.is_low_confidence(cls)
                else ParsedSectionStatus.CLASSIFIED
            )
            section_type_enum = self._cast_to_section_type(cls.candidate_type)
            result.append(
                section.model_copy(
                    update={
                        "section_type": section_type_enum,
                        "confidence": cls.confidence,
                        "section_status": new_status,
                        "classification_method": ClassificationMethod.RULE_BASED.value,
                    }
                )
            )
        return result

    # --- internal helpers ---

    def _find_hits(self, text: str) -> list[tuple[str, str]]:
        """Возвращает [(section_type, keyword), ...] для всех найденных совпадений."""
        hits: list[tuple[str, str]] = []
        for section_type, kw_patterns in self._patterns.items():
            for kw, pattern in kw_patterns:
                if pattern.search(text):
                    hits.append((section_type, kw))
                    break  # один keyword на тип достаточно
        return hits

    @staticmethod
    def _pick_best(hits: list[tuple[str, str]]) -> tuple[str, str]:
        """При множественных матчах — берём первый (стабильный порядок enum'а)."""
        # Сортируем по порядку в _KEYWORDS для детерминизма.
        order = list(_KEYWORDS.keys())
        hits_sorted = sorted(hits, key=lambda h: order.index(h[0]))
        return hits_sorted[0]

    @staticmethod
    def _cast_to_section_type(value: str) -> SectionType:
        for st in SectionType:
            if st.value == value:
                return st
        return SectionType.UNKNOWN

    @staticmethod
    def _build_classification(
        *,
        section_id: str,
        section_type: SectionType,
        confidence: float,
        reason: str,
    ) -> SectionClassification:
        return SectionClassification(
            classification_id=f"cls_{uuid.uuid4().hex[:12]}",
            section_id=section_id,
            candidate_type=section_type.value,  # SectionType → str
            confidence=confidence,
            method=ClassificationMethod.RULE_BASED,
            reason=reason,
            created_at=datetime.now(tz=UTC),
        )
