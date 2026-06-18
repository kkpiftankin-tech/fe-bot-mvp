"""Unit-тесты SectionBoundaryDetector + SectionClassifier (T-S04-017/018)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from schemas.setup.parsed_section import (
    ParsedSection,
    ParsedSectionStatus,
    SectionType,
)
from schemas.setup.section_classification import ClassificationMethod

from fe_bot.setup.parser.boundary import (
    SectionBoundary,
    SectionBoundaryDetector,
)
from fe_bot.setup.parser.classifier import SectionClassifier

pytestmark = pytest.mark.unit


def _section(
    *,
    section_id: str = "sec_001",
    title: str = "Generic",
    raw_text: str = "body",
    section_type: SectionType = SectionType.UNKNOWN,
    heading_path: list[str] | None = None,
    start_offset: int | None = None,
    end_offset: int | None = None,
) -> ParsedSection:
    return ParsedSection(
        section_id=section_id,
        parse_job_id="pj_001",
        source_document_id="src_001",
        section_index=0,
        parent_section_id=None,
        classification_method="rule_based",
        heading_path=heading_path or [],
        title=title,
        section_type=section_type,
        raw_text=raw_text,
        normalized_text=raw_text,
        start_offset=start_offset,
        end_offset=end_offset,
        content_hash=hashlib.sha256(raw_text.encode()).hexdigest(),
        confidence=0.5,
        created_at=datetime(2026, 6, 16, 10, 0, tzinfo=UTC),
    )


# ============================================================
# Boundary detector
# ============================================================


class TestBoundary:
    def test_detect_extracts_boundaries(self) -> None:
        det = SectionBoundaryDetector()
        sections = [
            _section(section_id="s1", start_offset=0, end_offset=10),
            _section(
                section_id="s2",
                title="Sub",
                heading_path=["Top"],
                start_offset=10,
                end_offset=25,
            ),
        ]
        boundaries = det.detect(sections)
        assert len(boundaries) == 2
        assert isinstance(boundaries[0], SectionBoundary)
        assert boundaries[1].level == 1

    def test_overlap_detection(self) -> None:
        sections = [
            _section(section_id="s1", start_offset=0, end_offset=15),
            _section(section_id="s2", start_offset=10, end_offset=25),  # overlap
        ]
        assert SectionBoundaryDetector.has_overlapping(sections) is True

    def test_no_overlap(self) -> None:
        sections = [
            _section(section_id="s1", start_offset=0, end_offset=10),
            _section(section_id="s2", start_offset=10, end_offset=20),
        ]
        assert SectionBoundaryDetector.has_overlapping(sections) is False

    def test_no_offsets_no_overlap(self) -> None:
        sections = [_section(section_id="s1")]  # offsets=None
        assert SectionBoundaryDetector.has_overlapping(sections) is False


# ============================================================
# Classifier
# ============================================================


class TestClassifierTitleMatch:
    def test_task_keyword_in_title_high_confidence(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="ML Tasks"))
        assert cls.candidate_type == SectionType.TASK.value
        assert cls.confidence == 0.9

    def test_schema_keyword_russian(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="Схема таблицы"))
        assert cls.candidate_type == SectionType.SCHEMA.value
        assert cls.confidence == 0.9

    def test_analytics_keyword(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="Performance analytics"))
        assert cls.candidate_type == SectionType.ANALYTICS.value

    def test_glossary_keyword_russian(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="Глоссарий терминов"))
        assert cls.candidate_type == SectionType.GLOSSARY.value

    def test_validation_keyword(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="Validation rules"))
        assert cls.candidate_type == SectionType.VALIDATION_RULE.value

    def test_question_keyword(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="Question templates"))
        assert cls.candidate_type == SectionType.QUESTION_TEMPLATE.value


class TestClassifierBodyMatch:
    def test_keyword_in_body_only_medium_confidence(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(
            _section(
                title="Untitled",
                raw_text="This describes a schema for our model inputs.",
            )
        )
        assert cls.candidate_type == SectionType.SCHEMA.value
        assert cls.confidence == 0.7


class TestClassifierNoMatch:
    def test_no_match_returns_unknown(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="Untitled", raw_text="Random unrelated text"))
        assert cls.candidate_type == SectionType.UNKNOWN.value
        assert cls.confidence == 0.5


class TestClassifierLowConfidence:
    def test_low_confidence_below_threshold(self) -> None:
        clf = SectionClassifier(confidence_threshold=0.8)
        cls = clf.classify(_section(title="Untitled", raw_text="Random text"))
        assert clf.is_low_confidence(cls) is True

    def test_high_confidence_above_threshold(self) -> None:
        clf = SectionClassifier(confidence_threshold=0.8)
        cls = clf.classify(_section(title="Tasks list"))
        assert clf.is_low_confidence(cls) is False


class TestClassifierApplyToSections:
    def test_apply_updates_section_type_and_status(self) -> None:
        clf = SectionClassifier()
        sections = [
            _section(section_id="s1", title="ML Tasks"),
            _section(section_id="s2", title="Random body"),
        ]
        result = clf.apply_to_sections(sections)
        assert result[0].section_type == SectionType.TASK
        assert result[0].section_status == ParsedSectionStatus.CLASSIFIED
        # No match → UNKNOWN + LOW_CONFIDENCE.
        assert result[1].section_type == SectionType.UNKNOWN
        assert result[1].section_status == ParsedSectionStatus.LOW_CONFIDENCE

    def test_apply_preserves_section_id_and_metadata(self) -> None:
        clf = SectionClassifier()
        original = _section(section_id="s_unique", title="ML Tasks")
        result = clf.apply_to_sections([original])
        assert result[0].section_id == "s_unique"
        assert result[0].source_document_id == original.source_document_id


class TestClassifierMethodIsRuleBased:
    def test_method_is_rule_based(self) -> None:
        clf = SectionClassifier()
        cls = clf.classify(_section(title="Tasks"))
        assert cls.method == ClassificationMethod.RULE_BASED

    def test_case_insensitive_matching(self) -> None:
        clf = SectionClassifier()
        cls_upper = clf.classify(_section(title="TASKS"))
        cls_lower = clf.classify(_section(title="tasks"))
        assert cls_upper.candidate_type == cls_lower.candidate_type == SectionType.TASK.value
