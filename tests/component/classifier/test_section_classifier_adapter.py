"""Component-тесты ClassifierTreeSectionClassifier (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.classifier.classification_result import (
    ClassifierPathStep,
    FragmentClassificationResult,
)
from schemas.setup.parsed_section import ParsedSection, ParsedSectionStatus

from fe_bot.classifier.section_classifier_adapter import ClassifierTreeSectionClassifier

pytestmark = pytest.mark.component


def _section(**overrides: object) -> ParsedSection:
    defaults: dict[str, object] = {
        "section_id": "sec_1",
        "parse_job_id": "pj_1",
        "source_document_id": "doc_1",
        "title": "Some section",
        "raw_text": "raw text about DNN architecture",
        "normalized_text": "raw text about dnn architecture",
        "confidence": 0.0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ParsedSection(**defaults)  # type: ignore[arg-type]


class _StubFragmentClassifier:
    def __init__(self, result: FragmentClassificationResult | None) -> None:
        self._result = result
        self.received_texts: list[str] = []

    def classify(self, fragment_text: str) -> FragmentClassificationResult | None:
        self.received_texts.append(fragment_text)
        return self._result


class TestClassifierTreeSectionClassifier:
    def test_populates_classifier_result_and_confidence(self) -> None:
        result = FragmentClassificationResult(
            tree_id="t1",
            path=[
                ClassifierPathStep(node_id="a", name="A", confidence=0.9),
                ClassifierPathStep(node_id="b", name="B", confidence=0.85),
            ],
            reached_leaf=True,
        )
        stub = _StubFragmentClassifier(result)
        adapter = ClassifierTreeSectionClassifier(classifier=stub)  # type: ignore[arg-type]

        [classified] = adapter.apply_to_sections([_section()])

        assert classified.classifier_result == result
        assert classified.confidence == 0.85
        assert classified.classification_method == "classifier_tree"
        assert classified.section_status == ParsedSectionStatus.CLASSIFIED

    def test_low_confidence_marks_section_status(self) -> None:
        result = FragmentClassificationResult(
            tree_id="t1",
            path=[ClassifierPathStep(node_id="a", name="A", confidence=0.3)],
            reached_leaf=False,
        )
        adapter = ClassifierTreeSectionClassifier(
            classifier=_StubFragmentClassifier(result),  # type: ignore[arg-type]
            confidence_threshold=0.5,
        )
        [classified] = adapter.apply_to_sections([_section()])
        assert classified.section_status == ParsedSectionStatus.LOW_CONFIDENCE

    def test_empty_path_leaves_section_low_confidence(self) -> None:
        result = FragmentClassificationResult(tree_id="t1", path=[], reached_leaf=False)
        adapter = ClassifierTreeSectionClassifier(
            classifier=_StubFragmentClassifier(result)  # type: ignore[arg-type]
        )
        [classified] = adapter.apply_to_sections([_section()])
        assert classified.confidence == 0.0
        assert classified.section_status == ParsedSectionStatus.LOW_CONFIDENCE
        assert classified.classifier_result == result

    def test_none_result_when_no_active_tree(self) -> None:
        adapter = ClassifierTreeSectionClassifier(
            classifier=_StubFragmentClassifier(None)  # type: ignore[arg-type]
        )
        [classified] = adapter.apply_to_sections([_section()])
        assert classified.classifier_result is None
        assert classified.section_status == ParsedSectionStatus.LOW_CONFIDENCE

    def test_uses_normalized_text_for_classification(self) -> None:
        stub = _StubFragmentClassifier(None)
        adapter = ClassifierTreeSectionClassifier(classifier=stub)  # type: ignore[arg-type]
        adapter.apply_to_sections([_section(normalized_text="normalized version")])
        assert stub.received_texts == ["normalized version"]
