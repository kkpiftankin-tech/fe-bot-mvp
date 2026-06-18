"""JSONParserStrategy (SETUP-04 / T-S04-012).

JSON-объект → секция per top-level key (если каждое значение — dict/list).
JSON-массив или скаляр → одна секция.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.registry import ParseFailedError


class JSONParserStrategy:
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
                f"JSON decode error: {exc}",
                error_code="JSON_PARSE_FAILED",
                filename=filename,
            ) from exc

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParseFailedError(
                f"Invalid JSON: {exc}",
                error_code="JSON_PARSE_FAILED",
                filename=filename,
            ) from exc

        now = datetime.now(tz=UTC)

        # JSON object с top-level keys → секция на ключ.
        if isinstance(parsed, dict):
            return self._parse_object(
                parsed=parsed,
                source_document_id=source_document_id,
                parse_job_id=parse_job_id,
                filename=filename,
                now=now,
            )
        # Иначе (array, scalar) — одна секция.
        return [
            self._make_single_section(
                value=parsed,
                text=text,
                source_document_id=source_document_id,
                parse_job_id=parse_job_id,
                filename=filename,
                now=now,
            )
        ]

    @staticmethod
    def _parse_object(
        *,
        parsed: dict[str, Any],
        source_document_id: str,
        parse_job_id: str,
        filename: str,
        now: datetime,
    ) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        for index, (key, value) in enumerate(parsed.items()):
            raw_text = json.dumps({key: value}, ensure_ascii=False, indent=2)
            structural: dict[str, Any] = {
                "json_type": (
                    "object"
                    if isinstance(value, dict)
                    else "array"
                    if isinstance(value, list)
                    else type(value).__name__
                ),
            }
            if isinstance(value, dict):
                structural["keys"] = list(value.keys())
            sections.append(
                ParsedSection(
                    section_id=f"sec_{uuid.uuid4().hex[:12]}",
                    parse_job_id=parse_job_id,
                    source_document_id=source_document_id,
                    section_index=index,
                    parent_section_id=None,
                    classification_method="rule_based",
                    heading_path=[key],
                    title=key,
                    section_type=SectionType.SCHEMA,
                    raw_text=raw_text,
                    normalized_text=raw_text,
                    confidence=0.8,
                    structural_payload=structural,
                    created_at=now,
                )
            )
        if not sections:
            # Пустой dict — одна заглушка.
            sections.append(
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
                    raw_text="{}",
                    normalized_text="{}",
                    confidence=0.5,
                    structural_payload={"json_type": "object", "keys": []},
                    created_at=now,
                )
            )
        return sections

    @staticmethod
    def _make_single_section(
        *,
        value: Any,
        text: str,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
        now: datetime,
    ) -> ParsedSection:
        json_type = "array" if isinstance(value, list) else type(value).__name__
        return ParsedSection(
            section_id=f"sec_{uuid.uuid4().hex[:12]}",
            parse_job_id=parse_job_id,
            source_document_id=source_document_id,
            section_index=0,
            parent_section_id=None,
            classification_method="rule_based",
            heading_path=[],
            title=filename,
            section_type=SectionType.SCHEMA,
            raw_text=text,
            normalized_text=text.strip(),
            confidence=0.7,
            structural_payload={"json_type": json_type},
            created_at=now,
        )
