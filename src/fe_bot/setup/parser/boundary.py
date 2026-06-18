"""SectionBoundaryDetector (SETUP-04 / T-S04-017).

Вспомогательная утилита для inspection уже разобранных секций.
Боундари детекция в основном выполняется внутри ParserStrategy
(Markdown через regex headings, DOCX через style heading, PDF — per page),
этот компонент предоставляет унифицированный read-only view.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from schemas.setup.parsed_section import ParsedSection


@dataclass(frozen=True, slots=True)
class SectionBoundary:
    """Границы одной секции в исходном тексте."""

    section_id: str
    start: int | None
    end: int | None
    title: str
    level: int  # depth of heading_path


class SectionBoundaryDetector:
    """Inspector извлечённых boundary'ев из уже разобранных секций.

    В отличие от ParserStrategy, не делает парсинг с нуля — работает
    с готовыми ParsedSection. Используется в Orchestrator для:
    - Логирования partial parse результатов;
    - Валидации overlapping offsets;
    - Frontend-стримминга progress (sections discovered).
    """

    def detect(self, sections: Sequence[ParsedSection]) -> list[SectionBoundary]:
        return [
            SectionBoundary(
                section_id=s.section_id,
                start=s.start_offset,
                end=s.end_offset,
                title=s.title,
                level=len(s.heading_path),
            )
            for s in sections
        ]

    @staticmethod
    def has_overlapping(sections: Sequence[ParsedSection]) -> bool:
        """Проверка целостности offsets — overlap может означать дефект парсера."""
        items = [
            (s.start_offset, s.end_offset)
            for s in sections
            if s.start_offset is not None and s.end_offset is not None
        ]
        items.sort()
        for (_, prev_end), (next_start, _) in zip(items, items[1:], strict=False):
            if prev_end is not None and next_start is not None and next_start < prev_end:
                return True
        return False
