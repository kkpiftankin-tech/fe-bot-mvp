"""XLSXParserStrategy (SETUP-04 / T-S04-016).

Каждый sheet → отдельная секция. headers + row_count + preview_rows
в structural_payload.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

import openpyxl  # type: ignore[import-untyped]
from openpyxl.utils.exceptions import (  # type: ignore[import-untyped]
    InvalidFileException,
)
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.registry import ParseFailedError

_PREVIEW_ROWS = 5


class XLSXParserStrategy:
    def parse(
        self,
        *,
        data: bytes,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
    ) -> list[ParsedSection]:
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except (InvalidFileException, Exception) as exc:
            raise ParseFailedError(
                f"XLSX read error: {exc}",
                error_code="TABLE_EXTRACTION_FAILED",
                filename=filename,
            ) from exc

        sheet_names = workbook.sheetnames
        if not sheet_names:
            raise ParseFailedError(
                "XLSX has no sheets",
                error_code="TABLE_EXTRACTION_FAILED",
                filename=filename,
            )

        sections: list[ParsedSection] = []
        now = datetime.now(tz=UTC)

        for index, sheet_name in enumerate(sheet_names):
            sheet = workbook[sheet_name]
            rows: list[list[str]] = []
            for row in sheet.iter_rows(values_only=True):
                rows.append(["" if v is None else str(v) for v in row])

            columns = rows[0] if rows else []
            data_rows = rows[1:] if rows else []
            preview = data_rows[:_PREVIEW_ROWS]

            lines = [f"Sheet: {sheet_name}"]
            if columns:
                lines.append(", ".join(columns))
            lines.extend(", ".join(r) for r in preview)
            raw_text = "\n".join(lines) or sheet_name

            sections.append(
                ParsedSection(
                    section_id=f"sec_{uuid.uuid4().hex[:12]}",
                    parse_job_id=parse_job_id,
                    source_document_id=source_document_id,
                    section_index=index,
                    parent_section_id=None,
                    classification_method="rule_based",
                    heading_path=[sheet_name],
                    title=sheet_name,
                    section_type=SectionType.SCHEMA,
                    raw_text=raw_text,
                    normalized_text=raw_text,
                    confidence=0.8,
                    structural_payload={
                        "sheet_name": sheet_name,
                        "columns": columns,
                        "row_count": len(data_rows),
                        "preview_rows": preview,
                    },
                    metadata={"sheet_name": sheet_name},
                    created_at=now,
                )
            )

        workbook.close()
        return sections
