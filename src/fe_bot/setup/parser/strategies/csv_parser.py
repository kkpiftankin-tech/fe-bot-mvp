"""CSVParserStrategy (SETUP-04 / T-S04-013).

Одна секция на весь CSV. structural_payload содержит columns + row_count +
preview_rows (первые 5 строк).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.registry import ParseFailedError

_PREVIEW_ROWS = 5


class CSVParserStrategy:
    def parse(
        self,
        *,
        data: bytes,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
    ) -> list[ParsedSection]:
        # Поддержка BOM (utf-8-sig сбрасывает BOM при декодировании).
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseFailedError(
                f"CSV decode error: {exc}",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            ) from exc

        if not text.strip():
            raise ParseFailedError(
                "Empty CSV document",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            )

        # Auto-detect разделителя.
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel  # fallback на запятую

        reader = csv.reader(io.StringIO(text), dialect)
        try:
            rows = list(reader)
        except csv.Error as exc:
            raise ParseFailedError(
                f"CSV parsing error: {exc}",
                error_code="TABLE_EXTRACTION_FAILED",
                filename=filename,
            ) from exc

        if not rows:
            raise ParseFailedError(
                "CSV has no rows",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            )

        columns = rows[0]
        data_rows = rows[1:]
        preview = data_rows[:_PREVIEW_ROWS]

        # raw_text — usable preview, не весь файл.
        lines = [", ".join(columns)]
        lines.extend(", ".join(row) for row in preview)
        raw_text = "\n".join(lines)

        return [
            ParsedSection(
                section_id=f"sec_{uuid.uuid4().hex[:12]}",
                parse_job_id=parse_job_id,
                source_document_id=source_document_id,
                section_index=0,
                parent_section_id=None,
                classification_method="rule_based",
                heading_path=[],
                title=filename,
                section_type=SectionType.SCHEMA,
                raw_text=raw_text,
                normalized_text=raw_text,
                confidence=0.85,
                structural_payload={
                    "columns": columns,
                    "row_count": len(data_rows),
                    "preview_rows": preview,
                },
                created_at=datetime.now(tz=UTC),
            )
        ]
