"""PlainTextParserStrategy (SETUP-04 / T-S04-012)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.registry import ParseFailedError


class PlainTextParserStrategy:
    """Plain text — одна секция на весь документ."""

    def parse(
        self,
        *,
        data: bytes,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
    ) -> list[ParsedSection]:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseFailedError(
                f"Text decode error: {exc}",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            ) from exc
        if not text.strip():
            raise ParseFailedError(
                "Empty text document",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            )

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
                section_type=SectionType.UNKNOWN,
                raw_text=text,
                normalized_text=text.strip(),
                start_offset=0,
                end_offset=len(text),
                confidence=0.7,
                created_at=datetime.now(tz=UTC),
            )
        ]
