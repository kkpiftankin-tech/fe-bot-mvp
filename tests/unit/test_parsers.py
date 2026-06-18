"""Тесты parser-dispatcher и форматов txt/csv/json + stubs (T-S01-018)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.parsed_section import SectionType
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus

from fe_bot.setup.parser.exceptions import (
    ParseFailedError,
    UnsupportedFormatError,
)
from fe_bot.setup.parser.service import DocumentParserService
from fe_bot.setup.parser.text_parsers import (
    parse_csv,
    parse_docx,
    parse_json,
    parse_pdf,
    parse_plain_text,
    parse_xlsx,
)
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.storage.artifact_service import InMemoryArtifactStorage

pytestmark = pytest.mark.unit


# ---------- text_parsers ----------


class TestPlainText:
    def test_simple(self) -> None:
        sections = parse_plain_text(
            source_document_id="src_1",
            setup_job_id="setup_1",
            text="Hello world",
        )
        assert len(sections) == 1
        assert sections[0].raw_text == "Hello world"

    def test_empty(self) -> None:
        with pytest.raises(ParseFailedError):
            parse_plain_text(source_document_id="src_1", setup_job_id="setup_1", text="   ")


class TestCSV:
    def test_simple(self) -> None:
        data = b"name,age\nAlice,30\nBob,25\n"
        sections = parse_csv(source_document_id="src_1", setup_job_id="setup_1", data=data)
        assert sections[0].section_type == SectionType.SCHEMA
        assert sections[0].metadata["columns"] == ["name", "age"]
        assert sections[0].metadata["row_count"] == 2

    def test_invalid_utf8(self) -> None:
        data = b"\xff\xfe\x00invalid"
        with pytest.raises(ParseFailedError, match="encoding"):
            parse_csv(source_document_id="s", setup_job_id="j", data=data)

    def test_empty_csv(self) -> None:
        with pytest.raises(ParseFailedError, match="Empty"):
            parse_csv(source_document_id="s", setup_job_id="j", data=b"")


class TestJSON:
    def test_object(self) -> None:
        data = b'{"a": 1, "b": [1, 2, 3]}'
        sections = parse_json(source_document_id="src_1", setup_job_id="setup_1", data=data)
        assert sections[0].section_type == SectionType.SCHEMA
        assert sections[0].metadata["kind"] == "object"
        assert sections[0].metadata["top_level_keys"] == ["a", "b"]

    def test_array(self) -> None:
        data = b"[1, 2, 3]"
        sections = parse_json(source_document_id="src_1", setup_job_id="setup_1", data=data)
        assert sections[0].metadata["kind"] == "array"

    def test_invalid_json(self) -> None:
        with pytest.raises(ParseFailedError, match="parse error"):
            parse_json(source_document_id="s", setup_job_id="j", data=b"{invalid")

    def test_large_json_truncated(self) -> None:
        data = b'"' + b"x" * 5000 + b'"'
        sections = parse_json(source_document_id="s", setup_job_id="j", data=data)
        assert "[truncated]" in sections[0].raw_text


class TestStubs:
    def test_pdf_unsupported(self) -> None:
        with pytest.raises(UnsupportedFormatError, match="PDF"):
            parse_pdf()

    def test_docx_unsupported(self) -> None:
        with pytest.raises(UnsupportedFormatError, match="DOCX"):
            parse_docx()

    def test_xlsx_unsupported(self) -> None:
        with pytest.raises(UnsupportedFormatError, match="XLSX"):
            parse_xlsx()


# ---------- DocumentParserService ----------


def _make_doc(
    content_type: str = "text/markdown",
    filename: str = "doc.md",
    checksum: str = "a" * 64,
) -> SourceDocument:
    return SourceDocument(
        source_document_id="src_test",
        setup_job_id="setup_test",
        filename=filename,
        content_type=content_type,
        storage_path=f"s3://source-documents/setup_test/src_test/{filename}",
        size_bytes=1,
        checksum=checksum,
        uploaded_by="u1",
        uploaded_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def parser_setup() -> tuple[DocumentParserService, InMemoryArtifactStorage, InMemorySourceRegistry]:
    storage = InMemoryArtifactStorage()
    registry = InMemorySourceRegistry()
    svc = DocumentParserService(artifact_storage=storage, source_registry=registry)
    return svc, storage, registry


class TestParserDispatcher:
    def test_dispatches_markdown(
        self,
        parser_setup: tuple[DocumentParserService, InMemoryArtifactStorage, InMemorySourceRegistry],
    ) -> None:
        svc, storage, registry = parser_setup
        doc = _make_doc()
        registry.add(doc)
        storage.upload(
            setup_job_id=doc.setup_job_id,
            source_document_id=doc.source_document_id,
            filename=doc.filename,
            content_type=doc.content_type,
            data=b"# Title\n\nbody",
        )
        sections = svc.parse(doc)
        assert len(sections) == 1
        assert sections[0].title == "Title"
        # status обновился
        updated = registry.get(doc.source_document_id)
        assert updated.status == SourceDocumentStatus.PARSED
        assert updated.parsed_at is not None

    def test_dispatches_json(
        self,
        parser_setup: tuple[DocumentParserService, InMemoryArtifactStorage, InMemorySourceRegistry],
    ) -> None:
        svc, storage, registry = parser_setup
        doc = _make_doc(content_type="application/json", filename="d.json")
        registry.add(doc)
        storage.upload(
            setup_job_id=doc.setup_job_id,
            source_document_id=doc.source_document_id,
            filename=doc.filename,
            content_type=doc.content_type,
            data=b'{"x":1}',
        )
        sections = svc.parse(doc)
        assert sections[0].section_type == SectionType.SCHEMA

    def test_unsupported_format_marks_failed(
        self,
        parser_setup: tuple[DocumentParserService, InMemoryArtifactStorage, InMemorySourceRegistry],
    ) -> None:
        svc, storage, registry = parser_setup
        doc = _make_doc(content_type="application/pdf", filename="d.pdf")
        registry.add(doc)
        storage.upload(
            setup_job_id=doc.setup_job_id,
            source_document_id=doc.source_document_id,
            filename=doc.filename,
            content_type=doc.content_type,
            data=b"%PDF-1.4",
        )
        with pytest.raises(UnsupportedFormatError):
            svc.parse(doc)
        updated = registry.get(doc.source_document_id)
        assert updated.status == SourceDocumentStatus.FAILED
        assert updated.error_message is not None
        assert "PDF" in updated.error_message

    def test_parse_failed_marks_failed(
        self,
        parser_setup: tuple[DocumentParserService, InMemoryArtifactStorage, InMemorySourceRegistry],
    ) -> None:
        svc, storage, registry = parser_setup
        doc = _make_doc(content_type="application/json", filename="bad.json")
        registry.add(doc)
        storage.upload(
            setup_job_id=doc.setup_job_id,
            source_document_id=doc.source_document_id,
            filename=doc.filename,
            content_type=doc.content_type,
            data=b"{not json",
        )
        with pytest.raises(ParseFailedError):
            svc.parse(doc)
        updated = registry.get(doc.source_document_id)
        assert updated.status == SourceDocumentStatus.FAILED
