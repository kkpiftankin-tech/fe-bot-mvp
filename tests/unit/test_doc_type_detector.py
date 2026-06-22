"""Unit-тесты DocTypeDetector (SETUP-05 / T-S05-015)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.rag_card_generation.doc_type_detector import (
    DocTypeDetector,
)

pytestmark = pytest.mark.unit


def _section(
    *,
    section_type: SectionType = SectionType.TASK,
    title: str = "Section",
    heading_path: list[str] | None = None,
    raw_text: str = "body",
) -> ParsedSection:
    return ParsedSection(
        section_id="sec_001",
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
        content_hash=hashlib.sha256(raw_text.encode()).hexdigest(),
        confidence=0.9,
        created_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


@pytest.fixture
def detector() -> DocTypeDetector:
    return DocTypeDetector()


class TestDirectMapping:
    @pytest.mark.parametrize(
        "section_type,expected_doc_type",
        [
            (SectionType.TASK, "task_card"),
            (SectionType.SCHEMA, "schema_card"),
            (SectionType.ANALYTICS, "analytics_card"),
            (SectionType.GLOSSARY, "field_definition_card"),
            (SectionType.VALIDATION_RULE, "validation_rule_card"),
            (SectionType.VALIDATION, "validation_rule_card"),
            (SectionType.QUESTION_TEMPLATE, "question_template_card"),
        ],
    )
    def test_direct_mapping(
        self,
        detector: DocTypeDetector,
        section_type: SectionType,
        expected_doc_type: str,
    ) -> None:
        d = detector.detect(_section(section_type=section_type))
        assert d.doc_type == expected_doc_type
        assert d.confidence == 0.9
        assert d.reason == "direct_mapping"
        assert d.is_valid


class TestFallback:
    def test_unknown_with_definition_keyword(self, detector: DocTypeDetector) -> None:
        d = detector.detect(_section(section_type=SectionType.UNKNOWN, title="Определение поля X"))
        assert d.doc_type == "field_definition_card"
        assert d.confidence == 0.5
        assert d.reason == "fallback_keyword"

    def test_other_with_glossary_in_heading(self, detector: DocTypeDetector) -> None:
        d = detector.detect(
            _section(
                section_type=SectionType.OTHER,
                title="X",
                heading_path=["Root", "Glossary"],
            )
        )
        assert d.doc_type == "field_definition_card"
        assert d.confidence == 0.5

    def test_unknown_no_signal_returns_invalid(self, detector: DocTypeDetector) -> None:
        d = detector.detect(_section(section_type=SectionType.UNKNOWN, title="Random content"))
        assert d.doc_type is None
        assert d.confidence == 0.0
        assert d.reason == "no_signal"
        assert not d.is_valid

    def test_domain_profile_no_signal_returns_invalid(self, detector: DocTypeDetector) -> None:
        d = detector.detect(_section(section_type=SectionType.DOMAIN_PROFILE, title="Domain X"))
        assert d.doc_type is None
