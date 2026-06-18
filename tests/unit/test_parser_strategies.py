"""Unit-тесты ParserStrategy реализаций (T-S04-011..016)."""

from __future__ import annotations

from pathlib import Path

import pytest
from schemas.setup.parsed_section import SectionType

from fe_bot.setup.parser.registry import ParseFailedError
from fe_bot.setup.parser.strategies import (
    CSVParserStrategy,
    DOCXParserStrategy,
    JSONParserStrategy,
    MarkdownParserStrategy,
    PDFParserStrategy,
    PlainTextParserStrategy,
    XLSXParserStrategy,
)

pytestmark = pytest.mark.unit

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "parser"


# ============================================================
# Markdown
# ============================================================


class TestMarkdown:
    def test_h1_h2_h3_hierarchy(self) -> None:
        text = b"# Top\n\n## Middle\n\n### Inner\n\nbody\n"
        sections = MarkdownParserStrategy().parse(
            data=text,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="x.md",
        )
        # 3 секции: Top, Middle, Inner.
        assert len(sections) == 3
        titles = [s.title for s in sections]
        assert titles == ["Top", "Middle", "Inner"]

    def test_section_index_is_sequential(self) -> None:
        text = b"# A\nbody\n## B\nbody\n## C\nbody\n"
        sections = MarkdownParserStrategy().parse(
            data=text,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="x.md",
        )
        assert [s.section_index for s in sections] == list(range(len(sections)))

    def test_parent_section_id_for_nested(self) -> None:
        text = b"# Parent\n\n## Child\n\n## Sibling\n"
        sections = MarkdownParserStrategy().parse(
            data=text,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="x.md",
        )
        parent = sections[0]
        child = sections[1]
        sibling = sections[2]
        assert child.parent_section_id == parent.section_id
        assert sibling.parent_section_id == parent.section_id

    def test_empty_raises(self) -> None:
        with pytest.raises(ParseFailedError):
            MarkdownParserStrategy().parse(
                data=b"",
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="empty.md",
            )

    def test_code_blocks_in_structural_payload(self) -> None:
        text = b"# Sec\n\n```python\nx = 1\n```\n"
        sections = MarkdownParserStrategy().parse(
            data=text,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="x.md",
        )
        assert "code_blocks" in sections[0].structural_payload
        assert "x = 1" in sections[0].structural_payload["code_blocks"][0]


# ============================================================
# Plain Text
# ============================================================


class TestPlainText:
    def test_single_section_full_content(self) -> None:
        text = b"Hello world\nLine 2"
        sections = PlainTextParserStrategy().parse(
            data=text,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="readme.txt",
        )
        assert len(sections) == 1
        assert sections[0].section_type == SectionType.UNKNOWN
        assert "Hello world" in sections[0].raw_text

    def test_empty_raises(self) -> None:
        with pytest.raises(ParseFailedError):
            PlainTextParserStrategy().parse(
                data=b"   \n",
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="empty.txt",
            )


# ============================================================
# JSON
# ============================================================


class TestJSON:
    def test_object_top_level_keys_become_sections(self) -> None:
        data = b'{"schema": {"a":1}, "tasks": [1,2], "name": "x"}'
        sections = JSONParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="config.json",
        )
        titles = [s.title for s in sections]
        assert titles == ["schema", "tasks", "name"]
        assert sections[0].structural_payload["json_type"] == "object"
        assert sections[1].structural_payload["json_type"] == "array"

    def test_array_single_section(self) -> None:
        sections = JSONParserStrategy().parse(
            data=b"[1,2,3]",
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="arr.json",
        )
        assert len(sections) == 1
        assert sections[0].structural_payload["json_type"] == "array"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ParseFailedError) as exc:
            JSONParserStrategy().parse(
                data=b"{invalid",
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="bad.json",
            )
        assert exc.value.error_code == "JSON_PARSE_FAILED"

    def test_empty_object_creates_placeholder(self) -> None:
        sections = JSONParserStrategy().parse(
            data=b"{}",
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="empty.json",
        )
        assert len(sections) == 1


# ============================================================
# CSV
# ============================================================


class TestCSV:
    def test_header_columns_in_payload(self) -> None:
        data = b"id,name,score\n1,a,0.5\n2,b,0.7\n"
        sections = CSVParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="data.csv",
        )
        assert sections[0].structural_payload["columns"] == ["id", "name", "score"]
        assert sections[0].structural_payload["row_count"] == 2

    def test_bom_handling(self) -> None:
        data = "﻿id,value\n1,foo\n".encode()
        sections = CSVParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="bom.csv",
        )
        # BOM не должен попасть в первую колонку.
        assert sections[0].structural_payload["columns"][0] == "id"

    def test_empty_raises(self) -> None:
        with pytest.raises(ParseFailedError):
            CSVParserStrategy().parse(
                data=b"",
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="empty.csv",
            )

    def test_header_only_row_count_zero(self) -> None:
        sections = CSVParserStrategy().parse(
            data=b"a,b,c\n",
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="headers.csv",
        )
        assert sections[0].structural_payload["row_count"] == 0


# ============================================================
# PDF
# ============================================================


class TestPDF:
    def test_pdf_text_layer_extracted(self) -> None:
        data = (_FIXTURES / "text-only.pdf").read_bytes()
        sections = PDFParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="text-only.pdf",
        )
        # Получаем хотя бы одну секцию с непустым raw_text.
        assert len(sections) >= 1
        joined = "".join(s.raw_text for s in sections)
        assert "Hello" in joined or "SETUP" in joined

    def test_pdf_scanned_raises_text_layer_not_found(self) -> None:
        data = (_FIXTURES / "scanned.pdf").read_bytes()
        with pytest.raises(ParseFailedError) as exc:
            PDFParserStrategy().parse(
                data=data,
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="scanned.pdf",
            )
        assert exc.value.error_code == "PDF_TEXT_LAYER_NOT_FOUND"

    def test_pdf_corrupted_raises(self) -> None:
        with pytest.raises(ParseFailedError):
            PDFParserStrategy().parse(
                data=b"not a pdf at all",
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="bad.pdf",
            )


# ============================================================
# DOCX
# ============================================================


class TestDOCX:
    def test_docx_heading_hierarchy(self) -> None:
        data = (_FIXTURES / "complex.docx").read_bytes()
        sections = DOCXParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="complex.docx",
        )
        titles = [s.title for s in sections]
        assert "Introduction" in titles
        assert "Details" in titles

    def test_docx_table_in_payload(self) -> None:
        data = (_FIXTURES / "complex.docx").read_bytes()
        sections = DOCXParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="complex.docx",
        )
        # Хотя бы одна секция содержит структурный payload с таблицей.
        assert any("tables" in s.structural_payload for s in sections)

    def test_docx_corrupted_raises(self) -> None:
        with pytest.raises(ParseFailedError) as exc:
            DOCXParserStrategy().parse(
                data=b"not a real docx",
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="bad.docx",
            )
        assert exc.value.error_code == "DOCX_EXTRACTION_FAILED"


# ============================================================
# XLSX
# ============================================================


class TestXLSX:
    def test_each_sheet_becomes_section(self) -> None:
        data = (_FIXTURES / "multi-sheet.xlsx").read_bytes()
        sections = XLSXParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="multi.xlsx",
        )
        # 2 sheets → 2 секции (Sensor, Weapon).
        titles = [s.title for s in sections]
        assert titles == ["Sensor", "Weapon"]

    def test_xlsx_columns_in_payload(self) -> None:
        data = (_FIXTURES / "multi-sheet.xlsx").read_bytes()
        sections = XLSXParserStrategy().parse(
            data=data,
            source_document_id="src_001",
            parse_job_id="pj_001",
            filename="multi.xlsx",
        )
        assert sections[0].structural_payload["columns"] == ["name", "value"]
        assert sections[0].structural_payload["row_count"] == 2

    def test_xlsx_corrupted_raises(self) -> None:
        with pytest.raises(ParseFailedError):
            XLSXParserStrategy().parse(
                data=b"not an xlsx",
                source_document_id="src_001",
                parse_job_id="pj_001",
                filename="bad.xlsx",
            )
