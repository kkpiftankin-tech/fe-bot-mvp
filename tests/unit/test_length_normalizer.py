"""Unit-тесты SectionLengthNormalizer (SETUP-04)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.parsed_section import ParsedSection, ParsedSectionStatus

from fe_bot.setup.parser.length_normalizer import SectionLengthNormalizer

pytestmark = pytest.mark.unit


def _section(
    *,
    section_id: str,
    index: int,
    title: str,
    text: str,
    heading_path: list[str] | None = None,
    parent_section_id: str | None = None,
) -> ParsedSection:
    return ParsedSection(
        section_id=section_id,
        parse_job_id="pj_1",
        source_document_id="src_1",
        section_index=index,
        parent_section_id=parent_section_id,
        heading_path=heading_path or [],
        title=title,
        section_status=ParsedSectionStatus.EXTRACTED,
        raw_text=text,
        normalized_text=text,
        start_offset=None,
        end_offset=None,
        confidence=0.75,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestMergeShortListItems:
    def test_merges_consecutive_numbered_list_items_until_threshold(self) -> None:
        sections = [
            _section(section_id="s1", index=0, title="Definitions", text="1. " + "a" * 100),
            _section(section_id="s2", index=1, title="Level 0", text="2. " + "b" * 100),
            _section(section_id="s3", index=2, title="Revision", text="3. " + "c" * 700),
        ]
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)
        result = norm.normalize(sections)

        assert len(result) == 1
        merged = result[0]
        assert merged.metadata["length_normalizer_merged_from"] == ["s1", "s2", "s3"]
        assert "a" * 100 in merged.raw_text
        assert "b" * 100 in merged.raw_text
        assert "c" * 700 in merged.raw_text

    def test_does_not_merge_distinct_real_headings_even_if_short(self) -> None:
        # Регрессия: 5 независимых заголовков ("# A".."# E") не должны
        # слипаться только потому, что у каждого короткое тело и общий
        # (пустой) heading_path.
        sections = [
            _section(section_id=f"s{i}", index=i, title=title, text=f"Body {title}")
            for i, title in enumerate(["A", "B", "C", "D", "E"])
        ]
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)
        result = norm.normalize(sections)

        assert len(result) == 5
        assert [s.section_id for s in result] == ["s0", "s1", "s2", "s3", "s4"]

    def test_short_standalone_list_item_without_neighbor_left_as_is(self) -> None:
        sections = [
            _section(section_id="s1", index=0, title="Intro", text="Intro body, not a list item."),
            _section(section_id="s2", index=1, title="Only item", text="1. short item"),
            _section(section_id="s3", index=2, title="Outro", text="Outro body, not a list item."),
        ]
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)
        result = norm.normalize(sections)

        assert [s.section_id for s in result] == ["s1", "s2", "s3"]
        assert result[1].raw_text == "1. short item"

    def test_trailing_remainder_merges_backward_into_previous_piece(self) -> None:
        sections = [
            _section(section_id="s1", index=0, title="A", text="1. " + "x" * 850),
            _section(section_id="s2", index=1, title="B", text="2. tiny tail"),
        ]
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)
        result = norm.normalize(sections)

        assert len(result) == 1
        assert result[0].metadata["length_normalizer_merged_from"] == ["s1", "s2"]
        assert "tiny tail" in result[0].raw_text

    def test_does_not_merge_across_different_heading_path(self) -> None:
        sections = [
            _section(
                section_id="s1",
                index=0,
                title="One",
                text="1. " + "x" * 50,
                heading_path=["Chapter 1"],
            ),
            _section(
                section_id="s2",
                index=1,
                title="One",
                text="1. " + "y" * 50,
                heading_path=["Chapter 2"],
            ),
        ]
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)
        result = norm.normalize(sections)

        assert [s.section_id for s in result] == ["s1", "s2"]

    def test_nested_backward_merge_keeps_all_source_ids_in_metadata(self) -> None:
        # s1+s2 сначала флашатся как один кусок (достигли threshold), затем
        # s3 — хвост рана короче threshold — мерджится НАЗАД в этот кусок.
        # Итоговый merged_from должен содержать все 3 id, а не 2.
        sections = [
            _section(section_id="s1", index=0, title="A", text="1. " + "x" * 500),
            _section(section_id="s2", index=1, title="B", text="2. " + "y" * 500),
            _section(section_id="s3", index=2, title="C", text="3. tail"),
        ]
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)
        result = norm.normalize(sections)

        assert len(result) == 1
        assert result[0].metadata["length_normalizer_merged_from"] == ["s1", "s2", "s3"]


class TestSplitLong:
    def test_splits_long_section_at_paragraph_boundaries(self) -> None:
        paragraphs = ["Para one. " * 50, "Para two. " * 50, "Para three. " * 50]
        text = "\n\n".join(paragraphs)
        section = _section(section_id="s1", index=0, title="Long", text=text)
        norm = SectionLengthNormalizer(min_chars=10, max_chars=600)

        result = norm.normalize([section])

        assert len(result) > 1
        assert all(len(s.raw_text) <= 600 for s in result)
        assert result[0].section_id == "s1"
        assert result[1].section_id == "s1_p2"
        assert result[1].metadata["length_normalizer_split_from"] == "s1"
        # Текст не потерян и не дублирован.
        assert "".join(s.raw_text for s in result).replace("\n\n", "") == text.replace("\n\n", "")

    def test_single_paragraph_exceeding_max_is_not_split(self) -> None:
        text = "One giant paragraph without blank lines. " * 200
        section = _section(section_id="s1", index=0, title="Long", text=text)
        norm = SectionLengthNormalizer(min_chars=10, max_chars=600)

        result = norm.normalize([section])

        assert len(result) == 1
        assert result[0].raw_text == text

    def test_section_within_bounds_untouched(self) -> None:
        section = _section(section_id="s1", index=0, title="Fine", text="x" * 1000)
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)

        result = norm.normalize([section])

        assert result == [section]


class TestReindex:
    def test_section_index_is_sequential_after_merge(self) -> None:
        sections = [
            _section(section_id="s1", index=0, title="A", text="1. " + "x" * 100),
            _section(section_id="s2", index=1, title="B", text="2. " + "y" * 900),
            _section(section_id="s3", index=2, title="Standalone", text="z" * 50),
        ]
        norm = SectionLengthNormalizer(min_chars=800, max_chars=4000)
        result = norm.normalize(sections)

        assert [s.section_index for s in result] == list(range(len(result)))


class TestConstructorValidation:
    def test_rejects_non_positive_min_chars(self) -> None:
        with pytest.raises(ValueError, match="min_chars"):
            SectionLengthNormalizer(min_chars=0, max_chars=100)

    def test_rejects_max_not_greater_than_min(self) -> None:
        with pytest.raises(ValueError, match="max_chars"):
            SectionLengthNormalizer(min_chars=100, max_chars=100)
