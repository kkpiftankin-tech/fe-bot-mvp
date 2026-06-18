"""Парсеры простых текстовых форматов: txt / csv / json (T-S01-018).

PDF / DOCX / XLSX — stubs с UnsupportedFormatError. Реальная реализация —
отдельная задача T-S01-018b, требующая pypdf / python-docx / openpyxl.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime

from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.exceptions import ParseFailedError, UnsupportedFormatError


def parse_plain_text(
    *,
    source_document_id: str,
    setup_job_id: str,
    text: str,
    filename: str = "document.txt",
) -> list[ParsedSection]:
    """Plain text → одна секция с raw_text = всё содержимое."""
    if not text.strip():
        raise ParseFailedError("Empty document", filename=filename)
    now = datetime.now(tz=UTC)
    return [
        ParsedSection(
            section_id=f"sec_{uuid.uuid4().hex[:12]}",
            source_document_id=source_document_id,
            parse_job_id=setup_job_id,  # SETUP-04: rename
            parent_section_id=None,
            classification_method="rule_based",
            title=filename,
            heading_path=[],
            section_type=SectionType.OTHER,
            raw_text=text,
            normalized_text=text.strip(),
            start_offset=0,
            end_offset=len(text),
            confidence=0.7,
            created_at=now,
            metadata={},
        )
    ]


def parse_csv(
    *,
    source_document_id: str,
    setup_job_id: str,
    data: bytes,
    filename: str = "document.csv",
) -> list[ParsedSection]:
    """CSV → одна секция type=SCHEMA с textified preview.

    Сохраняем заголовки колонок и первые ≤ 5 строк как preview.
    Полная таблица в metadata.row_count / columns.
    """
    try:
        text = data.decode("utf-8-sig")  # BOM handling
    except UnicodeDecodeError as exc:
        raise ParseFailedError(f"Invalid CSV encoding: {exc}", filename=filename) from exc

    try:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    except csv.Error as exc:
        raise ParseFailedError(f"CSV parse error: {exc}", filename=filename) from exc

    if not rows:
        raise ParseFailedError("Empty CSV", filename=filename)

    header = rows[0]
    body_rows = rows[1:]
    preview_rows = body_rows[:5]

    lines = [
        f"Columns: {', '.join(header)}",
        f"Rows: {len(body_rows)}",
        "",
        "Preview:",
    ]
    lines.extend(", ".join(row) for row in preview_rows)
    raw_text = "\n".join(lines)

    now = datetime.now(tz=UTC)
    return [
        ParsedSection(
            section_id=f"sec_{uuid.uuid4().hex[:12]}",
            source_document_id=source_document_id,
            parse_job_id=setup_job_id,  # SETUP-04: rename
            parent_section_id=None,
            classification_method="rule_based",
            title=filename,
            heading_path=[],
            section_type=SectionType.SCHEMA,
            raw_text=raw_text,
            normalized_text=raw_text,
            start_offset=0,
            end_offset=len(text),
            confidence=0.8,
            created_at=now,
            metadata={
                "columns": header,
                "row_count": len(body_rows),
                "format": "csv",
            },
        )
    ]


def parse_json(
    *,
    source_document_id: str,
    setup_job_id: str,
    data: bytes,
    filename: str = "document.json",
) -> list[ParsedSection]:
    """JSON → одна секция type=SCHEMA с pretty-printed preview."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseFailedError(f"Invalid JSON encoding: {exc}", filename=filename) from exc

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseFailedError(f"JSON parse error: {exc}", filename=filename) from exc

    # Pretty-print, ограниченный размером.
    pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
    truncated = pretty[:4000]
    if len(pretty) > 4000:
        truncated += "\n…\n[truncated]"

    if isinstance(parsed, dict):
        keys = list(parsed.keys())
        kind = "object"
    elif isinstance(parsed, list):
        keys = []
        kind = "array"
    else:
        keys = []
        kind = type(parsed).__name__

    now = datetime.now(tz=UTC)
    return [
        ParsedSection(
            section_id=f"sec_{uuid.uuid4().hex[:12]}",
            source_document_id=source_document_id,
            parse_job_id=setup_job_id,  # SETUP-04: rename
            parent_section_id=None,
            classification_method="rule_based",
            title=filename,
            heading_path=[],
            section_type=SectionType.SCHEMA,
            raw_text=truncated,
            normalized_text=truncated,
            start_offset=0,
            end_offset=len(text),
            confidence=0.8,
            created_at=now,
            metadata={
                "kind": kind,
                "top_level_keys": keys[:20],
                "format": "json",
            },
        )
    ]


# ---------- Stubs (T-S01-018b) ----------


def parse_pdf(**_kwargs: object) -> list[ParsedSection]:
    raise UnsupportedFormatError("PDF parsing not yet implemented (T-S01-018b, requires pypdf)")


def parse_docx(**_kwargs: object) -> list[ParsedSection]:
    raise UnsupportedFormatError(
        "DOCX parsing not yet implemented (T-S01-018b, requires python-docx)"
    )


def parse_xlsx(**_kwargs: object) -> list[ParsedSection]:
    raise UnsupportedFormatError("XLSX parsing not yet implemented (T-S01-018b, requires openpyxl)")
