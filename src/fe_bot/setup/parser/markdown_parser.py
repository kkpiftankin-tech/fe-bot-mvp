"""Markdown parser (T-S01-017).

Стратегия: разбивает Markdown на секции по заголовкам H1/H2/H3.
- YAML front matter (между `---`) пропускается из тела, но сохраняется в metadata.
- Каждая секция = ParsedSection с title, section_path[], raw/normalized text.
- Если заголовков нет, весь документ — одна секция с title = filename.

Source: SETUP-01 §11.2 (`parsed_sections`), docs/06-rag/ingestion-pipeline.md.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import yaml
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.exceptions import ParseFailedError

# Заголовки H1/H2/H3. Игнорируем те, что внутри code blocks (упрощённо).
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)

# Эвристика для определения SectionType из заголовка.
_SECTION_TYPE_KEYWORDS: tuple[tuple[str, SectionType], ...] = (
    ("task", SectionType.TASK),
    ("задач", SectionType.TASK),  # stem: задача / задачи / задаче / ...
    ("schema", SectionType.SCHEMA),
    ("схем", SectionType.SCHEMA),
    ("analytics", SectionType.ANALYTICS),
    ("аналитик", SectionType.ANALYTICS),
    ("glossary", SectionType.GLOSSARY),
    ("глоссарий", SectionType.GLOSSARY),
    ("validation", SectionType.VALIDATION),
    ("валидаци", SectionType.VALIDATION),
    ("domain", SectionType.DOMAIN_PROFILE),
    ("домен", SectionType.DOMAIN_PROFILE),
)


@dataclass(slots=True)
class _RawSection:
    level: int
    title: str
    start: int
    end: int = -1


def _detect_section_type(title: str) -> SectionType:
    lowered = title.lower()
    for keyword, section_type in _SECTION_TYPE_KEYWORDS:
        if keyword in lowered:
            return section_type
    return SectionType.OTHER


def _normalize(text: str) -> str:
    """Тривиальная нормализация: схлопывает множественные пробелы/переводы строк."""
    # Удалить trailing whitespace на каждой строке
    lines = [line.rstrip() for line in text.splitlines()]
    # Схлопнуть подряд пустые строки в одну
    out: list[str] = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                out.append("")
            prev_empty = True
        else:
            out.append(line)
            prev_empty = False
    return "\n".join(out).strip()


def _strip_front_matter(text: str) -> tuple[dict[str, object], str, int]:
    """Возвращает (front_matter, body, body_start_offset).

    Если front matter нет — возвращает ({}, text, 0).
    """
    if not text.startswith("---\n"):
        return {}, text, 0
    try:
        _, fm_block, body = text.split("---\n", 2)
    except ValueError as exc:
        raise ParseFailedError("Malformed YAML front matter (missing closing '---')") from exc
    try:
        parsed = yaml.safe_load(fm_block) or {}
    except yaml.YAMLError as exc:
        raise ParseFailedError(f"Invalid YAML front matter: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ParseFailedError("YAML front matter must be a mapping")
    body_offset = len("---\n") + len(fm_block) + len("---\n")
    return parsed, body, body_offset


def parse_markdown(
    *,
    source_document_id: str,
    setup_job_id: str,
    text: str,
    filename: str = "document.md",
) -> list[ParsedSection]:
    """Парсит Markdown-документ в список ParsedSection.

    Если заголовков H1/H2/H3 не найдено, весь документ — одна секция с title=filename.
    """
    if not text.strip():
        raise ParseFailedError("Empty document", filename=filename)

    front_matter, body, body_offset = _strip_front_matter(text)

    headings: list[_RawSection] = []
    for match in _HEADING_RE.finditer(body):
        level = len(match.group(1))
        title = match.group(2).strip()
        headings.append(_RawSection(level=level, title=title, start=match.start()))

    # Закрытие границ секций.
    for i, section in enumerate(headings):
        if i + 1 < len(headings):
            section.end = headings[i + 1].start
        else:
            section.end = len(body)

    sections: list[ParsedSection] = []
    now = datetime.now(tz=UTC)

    if not headings:
        # Документ без заголовков — одна секция целиком.
        raw_body = body.strip()
        normalized = _normalize(raw_body)
        sections.append(
            ParsedSection(
                section_id=f"sec_{uuid.uuid4().hex[:12]}",
                source_document_id=source_document_id,
                parse_job_id=setup_job_id,  # SETUP-04: rename of setup_job_id
                parent_section_id=None,
                classification_method="rule_based",
                title=filename,
                heading_path=[],
                section_type=SectionType.OTHER,
                raw_text=raw_body,
                normalized_text=normalized or raw_body,
                start_offset=body_offset,
                end_offset=body_offset + len(body),
                confidence=0.5,  # без заголовка — низкая уверенность
                created_at=now,
                metadata={"front_matter": front_matter} if front_matter else {},
            )
        )
        return sections

    # Поддерживаем path как stack текущих заголовков по уровням.
    path_stack: list[tuple[int, str]] = []
    for section in headings:
        # Сужаем stack до уровня выше текущего
        path_stack = [(lvl, t) for lvl, t in path_stack if lvl < section.level]
        section_path = [t for _, t in path_stack]
        path_stack.append((section.level, section.title))

        raw_body = body[section.start : section.end].strip()
        normalized = _normalize(raw_body)
        sections.append(
            ParsedSection(
                section_id=f"sec_{uuid.uuid4().hex[:12]}",
                source_document_id=source_document_id,
                parse_job_id=setup_job_id,  # SETUP-04: rename of setup_job_id
                parent_section_id=None,
                classification_method="rule_based",
                title=section.title,
                heading_path=section_path,
                section_type=_detect_section_type(section.title),
                raw_text=raw_body,
                normalized_text=normalized or raw_body,
                start_offset=body_offset + section.start,
                end_offset=body_offset + section.end,
                confidence=0.9,
                created_at=now,
                metadata={"front_matter": front_matter} if front_matter else {},
            )
        )
    return sections
