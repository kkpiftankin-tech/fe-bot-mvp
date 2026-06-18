"""PDFParserStrategy (SETUP-04 / T-S04-014).

Извлечение text layer через pypdf. Каждая страница — отдельная секция.
Scanned PDF (нет текстового слоя) → ParseErrorCode.PDF_TEXT_LAYER_NOT_FOUND.
OCR out of scope.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

import pypdf
from pypdf.errors import PdfReadError, PyPdfError
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.registry import ParseFailedError


class PDFParserStrategy:
    def parse(
        self,
        *,
        data: bytes,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
    ) -> list[ParsedSection]:
        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
        except (PdfReadError, PyPdfError, Exception) as exc:
            raise ParseFailedError(
                f"PDF read error: {exc}",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            ) from exc

        page_count = len(reader.pages)
        if page_count == 0:
            raise ParseFailedError(
                "PDF has no pages",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            )

        sections: list[ParsedSection] = []
        cumulative_offset = 0
        now = datetime.now(tz=UTC)
        non_empty_pages = 0

        for page_num, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001 — pypdf бросает разные
                raise ParseFailedError(
                    f"PDF page {page_num} extraction error: {exc}",
                    error_code="TEXT_EXTRACTION_FAILED",
                    filename=filename,
                ) from exc

            page_text = page_text.strip()
            if not page_text:
                # Пустая страница — не создаём секцию.
                continue
            non_empty_pages += 1

            structural: dict[str, object] = {"page_number": page_num}
            if page_num == 1:
                structural["page_count"] = page_count

            sections.append(
                ParsedSection(
                    section_id=f"sec_{uuid.uuid4().hex[:12]}",
                    parse_job_id=parse_job_id,
                    source_document_id=source_document_id,
                    section_index=len(sections),
                    parent_section_id=None,
                    classification_method="rule_based",
                    heading_path=[],
                    title=f"Page {page_num}",
                    section_type=SectionType.UNKNOWN,
                    raw_text=page_text,
                    normalized_text=page_text,
                    start_offset=cumulative_offset,
                    end_offset=cumulative_offset + len(page_text),
                    confidence=0.6,
                    structural_payload=structural,
                    metadata={"page_number": page_num},
                    created_at=now,
                )
            )
            cumulative_offset += len(page_text) + 1  # +1 for delimiter

        if non_empty_pages == 0:
            # Все страницы пусты → scanned PDF без OCR.
            raise ParseFailedError(
                "PDF has no extractable text layer (likely scanned, OCR not supported)",
                error_code="PDF_TEXT_LAYER_NOT_FOUND",
                filename=filename,
            )

        return sections
