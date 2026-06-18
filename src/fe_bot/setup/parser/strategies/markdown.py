"""MarkdownParserStrategy (SETUP-04 / T-S04-011).

Адаптация существующего markdown_parser.py под ParserStrategy Protocol.
Добавляет section_index + parent_section_id + structural_payload.code_blocks.
"""

from __future__ import annotations

import re

from schemas.setup.parsed_section import ParsedSection

from fe_bot.setup.parser.markdown_parser import parse_markdown
from fe_bot.setup.parser.registry import ParseFailedError

_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z0-9_+\-]*)\n(.*?)```", re.DOTALL)


class MarkdownParserStrategy:
    """Markdown / TXT-подобный текст с headings."""

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
                f"Markdown decode error: {exc}",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            ) from exc

        if not text.strip():
            raise ParseFailedError(
                "Empty markdown document",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            )

        sections = parse_markdown(
            text=text,
            source_document_id=source_document_id,
            setup_job_id=parse_job_id,  # adapter: markdown_parser ещё ждёт setup_job_id
            filename=filename,
        )

        # Постпроцессинг: section_index + parent_section_id + structural_payload.
        return self._enrich(sections)

    @staticmethod
    def _enrich(sections: list[ParsedSection]) -> list[ParsedSection]:
        enriched: list[ParsedSection] = []
        # Map heading_path length → последний section_id на этом уровне.
        # Например, для H2 под H1 родитель — последний H1.
        parent_at_depth: dict[int, str] = {}

        for index, section in enumerate(sections):
            depth = len(section.heading_path)
            parent_section_id: str | None = None
            if depth > 0:
                # Родитель — секция на (depth-1) уровне (последняя зарегистрированная).
                parent_section_id = parent_at_depth.get(depth - 1)

            # Code blocks → structural_payload.
            code_blocks = _CODE_BLOCK_RE.findall(section.raw_text)
            structural = dict(section.structural_payload)
            if code_blocks:
                structural["code_blocks"] = code_blocks

            updated = section.model_copy(
                update={
                    "section_index": index,
                    "parent_section_id": parent_section_id,
                    "structural_payload": structural,
                }
            )
            enriched.append(updated)
            # Регистрируем эту секцию как потенциального родителя для глубже.
            parent_at_depth[depth] = updated.section_id

        return enriched
