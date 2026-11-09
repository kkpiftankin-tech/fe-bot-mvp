"""Unit-тесты ParserStrategy реализаций (T-S04-011..016)."""

from __future__ import annotations

import io
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


def _make_pdf(pages: list[list[str]]) -> bytes:
    """Собирает минимальный валидный PDF 1.4 с заданными строками на
    страницах (по одной строке текста на Tj-вызов, шрифт Helvetica).

    pypdf не умеет генерировать PDF с текстом (только читать/сводить), а
    reportlab/fpdf не входят в зависимости проекта — поэтому здесь
    собирается raw PDF byte-syntax напрямую. Используется только тестами
    PDFParserStrategy (SETUP-04 / T-S04-014 structure-aware rewrite).
    """
    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    content_ids: list[int] = []
    for lines in pages:
        y = 750
        parts = [b"BT"]
        for line in lines:
            esc = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            parts.append(b"/F1 12 Tf")
            parts.append(f"1 0 0 1 72 {y} Tm".encode())
            parts.append(f"({esc}) Tj".encode())
            y -= 16
        parts.append(b"ET")
        stream = b"\n".join(parts)
        content_ids.append(
            add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        )

    pages_placeholder = add(b"PLACEHOLDER")
    page_ids = [
        add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_placeholder, font_id, content_ids[i])
        )
        for i in range(len(pages))
    ]
    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    objects[pages_placeholder - 1] = b"<< /Type /Pages /Kids [ %s ] /Count %d >>" % (
        kids,
        len(page_ids),
    )
    catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_placeholder)

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0] * (len(objects) + 1)
    for i, body in enumerate(objects, start=1):
        offsets[i] = out.tell()
        out.write(b"%d 0 obj\n" % i)
        out.write(body)
        out.write(b"\nendobj\n")
    xref_offset = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for i in range(1, len(objects) + 1):
        out.write(b"%010d 00000 n \n" % offsets[i])
    out.write(b"trailer\n<< /Size %d /Root %d 0 R >>\n" % (len(objects) + 1, catalog_id))
    out.write(b"startxref\n%d\n" % xref_offset)
    out.write(b"%%EOF")
    return out.getvalue()


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

    def test_pdf_no_headings_falls_back_to_per_page(self) -> None:
        # Совместимость со старым поведением (T-S04-014 baseline): плоский
        # PDF без нумерации/ключевых слов — секция на страницу.
        data = _make_pdf([["Just some flat body text."], ["More flat text here."]])
        sections = PDFParserStrategy().parse(
            data=data, source_document_id="src_001", parse_job_id="pj_001", filename="flat.pdf"
        )
        assert len(sections) == 2
        assert sections[0].title == "Page 1"
        assert sections[1].title == "Page 2"
        assert sections[0].heading_path == []

    def test_decimal_numbering_builds_heading_hierarchy(self) -> None:
        data = _make_pdf(
            [
                ["1 Introduction", "Top-level chapter body text goes here."],
                ["1.1 Background", "Nested subsection body text."],
                ["1.2 Scope", "Another subsection at the same level."],
                ["2 Methods", "Second top-level chapter body."],
            ]
        )
        sections = PDFParserStrategy().parse(
            data=data, source_document_id="src_001", parse_job_id="pj_001", filename="numbered.pdf"
        )
        titles = [s.title for s in sections]
        assert "Background" in titles
        assert "Scope" in titles
        background = next(s for s in sections if s.title == "Background")
        scope = next(s for s in sections if s.title == "Scope")
        # "1 Introduction" — bare-number (без точки), попадает под dedup-риск
        # и сам по себе не гарантирован, но его ДЕТИ обязаны знать родителя.
        assert background.heading_path == scope.heading_path
        assert background.heading_path  # непустой — вложены под "Introduction".
        assert "Background" in background.raw_text or "Nested subsection" in background.raw_text

    def test_toc_dot_leader_lines_are_not_headings(self) -> None:
        data = _make_pdf(
            [
                [
                    "x Contents",
                    "1 Introduction ....................................................1",
                    "2 Methods .........................................................15",
                ],
                ["1 Introduction", "Real chapter body text starts here."],
            ]
        )
        sections = PDFParserStrategy().parse(
            data=data, source_document_id="src_001", parse_job_id="pj_001", filename="toc.pdf"
        )
        titles = [s.title for s in sections]
        # dot-leader записи из оглавления НЕ должны стать отдельными секциями.
        assert not any("......." in t for t in titles)

    def test_toc_title_page_tagged_as_zone(self) -> None:
        data = _make_pdf(
            [
                ["Contents", "1 Introduction .............................................1"],
                ["1 Introduction", "Body text of the introduction chapter."],
            ]
        )
        sections = PDFParserStrategy().parse(
            data=data, source_document_id="src_001", parse_job_id="pj_001", filename="toc2.pdf"
        )
        toc_sections = [s for s in sections if s.structural_payload.get("zone") == "toc"]
        assert len(toc_sections) == 1
        assert toc_sections[0].confidence < 0.5

    def test_references_heading_tagged_as_zone(self) -> None:
        data = _make_pdf(
            [
                ["1 Introduction", "Body text of the introduction."],
                ["References", "A. Author, Some Paper, 2020."],
            ]
        )
        sections = PDFParserStrategy().parse(
            data=data, source_document_id="src_001", parse_job_id="pj_001", filename="refs.pdf"
        )
        refs = [s for s in sections if s.structural_payload.get("zone") == "references"]
        assert len(refs) == 1
        assert refs[0].title == "References"
        assert refs[0].confidence < 0.5

    def test_chapter_keyword_heading_detected(self) -> None:
        data = _make_pdf(
            [
                ["Chapter 1 Overview", "Body of the overview chapter."],
                ["Chapter 2 Details", "Body of the details chapter."],
            ]
        )
        sections = PDFParserStrategy().parse(
            data=data, source_document_id="src_001", parse_job_id="pj_001", filename="chapters.pdf"
        )
        titles = [s.title for s in sections]
        assert "Overview" in titles
        assert "Details" in titles

    def test_repeated_running_header_is_dropped(self) -> None:
        # "N Title" без подуровня, повторяющийся дословно на каждой странице,
        # — это running header, а не серия отдельных глав; должен быть
        # отброшен целиком (реальный кейс: Handbook of Multisensor Data
        # Fusion, где "N Book Title" печатается почти на каждой странице).
        running_header = "Some Book Title"
        data = _make_pdf(
            [
                [f"1 {running_header}", "Page one body text."],
                [f"2 {running_header}", "Page two body text."],
                [f"3 {running_header}", "Page three body text."],
                ["1.1 Real Subsection", "Real nested content."],
            ]
        )
        sections = PDFParserStrategy().parse(
            data=data, source_document_id="src_001", parse_job_id="pj_001", filename="header.pdf"
        )
        assert running_header not in [s.title for s in sections]
        # Реальный контент со страниц не потерян — просто без heading-обёртки.
        joined = "".join(s.raw_text for s in sections)
        assert "Page one body text." in joined
        assert "Page two body text." in joined
        titles = [s.title for s in sections]
        assert "Real Subsection" in titles


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
