"""Тесты Markdown parser (T-S01-017)."""

from __future__ import annotations

import pytest
from schemas.setup.parsed_section import SectionType

from fe_bot.setup.parser.exceptions import ParseFailedError
from fe_bot.setup.parser.markdown_parser import parse_markdown

pytestmark = pytest.mark.unit


def _parse(text: str, filename: str = "doc.md"):
    return parse_markdown(
        source_document_id="src_1",
        setup_job_id="setup_1",
        text=text,
        filename=filename,
    )


class TestBasicParsing:
    def test_single_h1(self) -> None:
        sections = _parse("# Title\n\nBody.")
        assert len(sections) == 1
        assert sections[0].title == "Title"
        assert sections[0].section_path == []
        assert "Body" in sections[0].raw_text

    def test_h1_h2_nesting(self) -> None:
        text = "# A\n\nintro\n\n## B\n\ntext B\n\n## C\n\ntext C"
        sections = _parse(text)
        assert len(sections) == 3
        assert [s.title for s in sections] == ["A", "B", "C"]
        assert sections[0].section_path == []
        assert sections[1].section_path == ["A"]
        assert sections[2].section_path == ["A"]

    def test_h1_h2_h3_nesting(self) -> None:
        text = "# Top\n\n## Mid\n\n### Leaf\n\nbody"
        sections = _parse(text)
        assert sections[2].section_path == ["Top", "Mid"]
        assert sections[2].title == "Leaf"

    def test_no_headings_single_section(self) -> None:
        sections = _parse("Just some text without any headings.")
        assert len(sections) == 1
        assert sections[0].title == "doc.md"
        assert sections[0].confidence == 0.5  # low — no heading

    def test_empty_document_raises(self) -> None:
        with pytest.raises(ParseFailedError, match="Empty"):
            _parse("")
        with pytest.raises(ParseFailedError):
            _parse("   \n\n   ")


class TestSectionType:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Task description", SectionType.TASK),
            ("Описание задачи", SectionType.TASK),
            ("Schema definition", SectionType.SCHEMA),
            ("Схема данных", SectionType.SCHEMA),
            ("Sensor analytics", SectionType.ANALYTICS),
            ("Аналитика операций", SectionType.ANALYTICS),
            ("Glossary", SectionType.GLOSSARY),
            ("Validation rules", SectionType.VALIDATION),
            ("Domain context", SectionType.DOMAIN_PROFILE),
            ("Something else", SectionType.OTHER),
        ],
    )
    def test_section_type_detection(self, title: str, expected: SectionType) -> None:
        sections = _parse(f"# {title}\n\nbody")
        assert sections[0].section_type == expected


class TestYamlFrontMatter:
    def test_with_front_matter(self) -> None:
        text = "---\ntitle: My Doc\nversion: 1.0\n---\n\n# Title\n\nbody"
        sections = _parse(text)
        assert sections[0].metadata == {"front_matter": {"title": "My Doc", "version": 1.0}}
        # start_offset должен учитывать длину front matter
        assert sections[0].start_offset is not None
        assert sections[0].start_offset > 0

    def test_no_front_matter(self) -> None:
        sections = _parse("# Title\n\nbody")
        assert sections[0].metadata == {}

    def test_malformed_front_matter_no_closing(self) -> None:
        with pytest.raises(ParseFailedError, match="Malformed YAML"):
            _parse("---\ntitle: x\n# Title\n\nbody")

    def test_invalid_yaml(self) -> None:
        with pytest.raises(ParseFailedError, match="Invalid YAML"):
            _parse("---\n[: unbalanced\n---\n\n# Title\n\nbody")

    def test_front_matter_not_mapping(self) -> None:
        with pytest.raises(ParseFailedError, match="mapping"):
            _parse("---\n- list\n- items\n---\n\n# Title\n\nbody")


class TestOffsets:
    def test_offsets_consistent(self) -> None:
        text = "# A\nbody A\n## B\nbody B"
        sections = _parse(text)
        for sec in sections:
            assert sec.start_offset is not None and sec.end_offset is not None
            assert sec.end_offset >= sec.start_offset


class TestNormalization:
    def test_collapses_multiple_blank_lines(self) -> None:
        text = "# T\n\n\n\nbody1\n\n\n\nbody2"
        sections = _parse(text)
        # Не должно быть подряд 3+ переводов строки
        assert "\n\n\n" not in sections[0].normalized_text

    def test_strips_trailing_whitespace(self) -> None:
        text = "# T   \n\nbody   \n"
        sections = _parse(text)
        assert "body   " not in sections[0].normalized_text
