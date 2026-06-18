"""DOCXParserStrategy (SETUP-04 / T-S04-015).

Параграфы со стилем Heading 1/2/3 → границы секций. Таблицы → structural_payload.
"""

from __future__ import annotations

import io
import re
import uuid
from datetime import UTC, datetime

import docx
from docx.opc.exceptions import PackageNotFoundError
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.registry import ParseFailedError

_HEADING_RE = re.compile(r"^Heading (\d+)$")


class DOCXParserStrategy:
    def parse(
        self,
        *,
        data: bytes,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
    ) -> list[ParsedSection]:
        try:
            document = docx.Document(io.BytesIO(data))
        except (PackageNotFoundError, Exception) as exc:
            raise ParseFailedError(
                f"DOCX extraction error: {exc}",
                error_code="DOCX_EXTRACTION_FAILED",
                filename=filename,
            ) from exc

        # Собираем все параграфы + помечаем уровень heading (None если обычный).
        items: list[tuple[int | None, str]] = []
        for para in document.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            level = self._heading_level(para.style.name if para.style else None)
            items.append((level, text))

        # Все таблицы → структурный payload первой секции (для MVP).
        tables: list[list[list[str]]] = []
        for table in document.tables:
            tables.append([[cell.text.strip() for cell in row.cells] for row in table.rows])

        now = datetime.now(tz=UTC)
        sections: list[ParsedSection] = []
        parent_at_depth: dict[int, str] = {}

        # Если нет headings — одна секция со всем текстом.
        has_headings = any(lvl is not None for lvl, _ in items)
        if not has_headings:
            if not items:
                raise ParseFailedError(
                    "DOCX has no extractable text",
                    error_code="DOCX_EXTRACTION_FAILED",
                    filename=filename,
                )
            full_text = "\n".join(text for _, text in items)
            sections.append(
                self._make_section(
                    section_id=f"sec_{uuid.uuid4().hex[:12]}",
                    source_document_id=source_document_id,
                    parse_job_id=parse_job_id,
                    section_index=0,
                    parent_section_id=None,
                    heading_path=[],
                    title=filename,
                    text=full_text,
                    structural={"tables": tables} if tables else {},
                    now=now,
                )
            )
            return sections

        # Разбиваем по headings.
        current_title: str | None = None
        current_path: list[str] = []
        current_body: list[str] = []
        current_level: int = 0

        def flush() -> None:
            nonlocal current_body
            if current_title is None:
                return
            section_id = f"sec_{uuid.uuid4().hex[:12]}"
            parent_id = parent_at_depth.get(current_level - 1) if current_level > 1 else None
            text = "\n".join(current_body).strip() or current_title
            payload: dict[str, object] = {}
            # Первая секция получает таблицы (MVP-упрощение).
            if not sections and tables:
                payload["tables"] = tables
            sections.append(
                self._make_section(
                    section_id=section_id,
                    source_document_id=source_document_id,
                    parse_job_id=parse_job_id,
                    section_index=len(sections),
                    parent_section_id=parent_id,
                    heading_path=list(current_path),
                    title=current_title,
                    text=text,
                    structural=payload,
                    now=now,
                )
            )
            parent_at_depth[current_level] = section_id
            current_body = []

        for level, text in items:
            if level is not None:
                # Новый heading → flush предыдущей секции и начать новую.
                flush()
                # Усекаем path до уровня выше.
                current_path = [p for p in current_path[: max(level - 1, 0)]]
                current_path.append(text)
                current_title = text
                current_level = level
            else:
                current_body.append(text)
        flush()

        return sections

    @staticmethod
    def _heading_level(style_name: str | None) -> int | None:
        if not style_name:
            return None
        match = _HEADING_RE.match(style_name)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _make_section(
        *,
        section_id: str,
        source_document_id: str,
        parse_job_id: str,
        section_index: int,
        parent_section_id: str | None,
        heading_path: list[str],
        title: str,
        text: str,
        structural: dict[str, object],
        now: datetime,
    ) -> ParsedSection:
        return ParsedSection(
            section_id=section_id,
            parse_job_id=parse_job_id,
            source_document_id=source_document_id,
            section_index=section_index,
            parent_section_id=parent_section_id,
            classification_method="rule_based",
            heading_path=heading_path,
            title=title,
            section_type=SectionType.UNKNOWN,
            raw_text=text,
            normalized_text=text,
            confidence=0.75,
            structural_payload=structural,
            created_at=now,
        )
