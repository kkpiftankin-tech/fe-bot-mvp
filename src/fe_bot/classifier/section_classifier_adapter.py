"""ClassifierTreeSectionClassifier (SETUP-13 / ADR-HTC-09).

Адаптер, оборачивающий ``FragmentClassifier`` под интерфейс
``SectionClassifier.apply_to_sections(list[ParsedSection]) ->
list[ParsedSection]`` — тот же контракт, что и legacy
``HierarchicalSectionClassifier`` (SETUP-12), которую эта реализация
заменяет: ``FE_BOT_TAXONOMY_MODE=llm`` теперь строит этот классификатор
(см. ``fe_bot.api.dependencies._build_section_classifier``).

В отличие от SETUP-12 (фиксированные 3 уровня × 10 бит), дерево SETUP-13
произвольной глубины/ширины — поэтому результат хранится не в
``ClassificationState`` (bitmap), а в отдельном поле
``ParsedSection.classifier_result`` (путь узлов + confidence на каждом
уровне). Legacy ``section_type`` не derive'ится из нового дерева (нет
надёжного маппинга произвольных классов на старый закрытый enum) —
остаётся ``OTHER``; фактическая классификация — в ``classifier_result``.
"""

from __future__ import annotations

from schemas.setup.parsed_section import ParsedSection, ParsedSectionStatus, SectionType

from fe_bot.classifier.fragment_classifier import FragmentClassifier

_CLASSIFICATION_METHOD = "classifier_tree"


class ClassifierTreeSectionClassifier:
    def __init__(
        self, *, classifier: FragmentClassifier, confidence_threshold: float = 0.5
    ) -> None:
        self._classifier = classifier
        self._threshold = confidence_threshold

    def apply_to_sections(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        return [self._classify_one(section) for section in sections]

    def _classify_one(self, section: ParsedSection) -> ParsedSection:
        text = section.normalized_text or section.raw_text
        result = self._classifier.classify(text)

        if result is None or not result.path:
            # Нет активного дерева, или LLM не смогла уверенно отнести
            # фрагмент ни к одному классу верхнего уровня.
            return section.model_copy(
                update={
                    "section_type": SectionType.UNKNOWN,
                    "confidence": 0.0,
                    "section_status": ParsedSectionStatus.LOW_CONFIDENCE,
                    "classification_method": _CLASSIFICATION_METHOD,
                    "classifier_result": result,
                }
            )

        confidence = result.overall_confidence
        section_status = (
            ParsedSectionStatus.LOW_CONFIDENCE
            if confidence < self._threshold
            else ParsedSectionStatus.CLASSIFIED
        )
        return section.model_copy(
            update={
                "section_type": SectionType.OTHER,
                "confidence": confidence,
                "section_status": section_status,
                "classification_method": _CLASSIFICATION_METHOD,
                "classifier_result": result,
            }
        )
