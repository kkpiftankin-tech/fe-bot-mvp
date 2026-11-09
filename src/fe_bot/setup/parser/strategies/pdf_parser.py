"""PDFParserStrategy (SETUP-04 / T-S04-014, structure-aware rewrite).

Извлекает текстовый слой через pypdf и делит документ на секции по
РЕАЛЬНОЙ структуре (заголовки), а не по границам страниц:

1. Primary signal — нумерация в начале строки: ``"1.2 Title"``,
   ``"Chapter 3"``, ``"Глава 3"``, ``"Part II"``, ``"Часть II"``.
2. Fallback-эвристика для "оторванных" номеров глав: реальные книжные
   PDF нередко рендерят номер главы отдельной декоративной строкой,
   а название — следующей строкой (подтверждено на реальном Handbook
   of Multisensor Data Fusion: страница начинается с ``"1\\n1\\nTitle"``).
   Font-size через pypdf visitor API для этого не годится — на этом же
   документе он оказался нерабочим (``font_size`` всегда возвращает
   1.0, реальный масштаб зашит в text-matrix, а не в ``Tf``), поэтому
   вместо font-size используется структурный сигнал "голый номер +
   короткая Title-Case строка сразу за ним".
3. Table of Contents и chapter-level mini-TOC — строки вида
   ``"1.1 Introduction ....... 1"`` (текст + dot-leader + номер
   страницы) распознаются и исключаются из heading-detection: иначе
   номера из оглавления дают ложные срабатывания decimal-паттерна.
4. References/Bibliography — заголовок, совпадающий с ключевыми
   словами (``References``, ``Литература``, ``Список литературы`` и
   т.п.), помечается ``structural_payload["zone"] = "references"`` и
   получает заниженный confidence — это не контентная секция для
   RAG-карточек.

Fallback без потери данных: если во всём документе не найдено ни
одного заголовка — поведение как раньше (T-S04-014 baseline): одна
секция на страницу. Это покрывает плоские PDF без видимой структуры
(сканы с OCR-слоем, письма, формы).

Scanned PDF (нет текстового слоя) → ParseErrorCode.PDF_TEXT_LAYER_NOT_FOUND.
OCR out of scope.
"""

from __future__ import annotations

import io
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

import pypdf
from pypdf.errors import DependencyError, PdfReadError, PyPdfError
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.registry import ParseFailedError

# ---------------------------------------------------------------------------
# Heading detection heuristics
# ---------------------------------------------------------------------------

_MAX_TITLE_LEN = 90

# TOC / mini-TOC entry: "<текст> <....dot-leader....> <номер страницы>".
# Проверяется ПЕРВОЙ — такие строки исключаются из heading-detection,
# иначе "1.1 Introduction .......... 1" даст ложное срабатывание.
_TOC_LINE_RE = re.compile(r"^.{2,}?\.{3,}.*\d{1,4}\s*$")

# Decimal-нумерация: "1 Title", "1.2 Title", "1.2.3 Title" (до 4 уровней).
_DECIMAL_HEADING_RE = re.compile(
    rf"^(?P<num>\d{{1,2}}(?:\.\d{{1,2}}){{0,3}})\.?\s+(?P<title>[A-ZА-ЯЁ][^\n]{{1,{_MAX_TITLE_LEN}}})$"
)

# "Chapter N" / "Глава N" / "Part N" / "Часть N" (± Roman numerals).
_CHAPTER_HEADING_RE = re.compile(
    r"^(?P<kind>Chapter|CHAPTER|Глава|ГЛАВА|Part|PART|Часть|ЧАСТЬ)\s+"
    rf"(?P<num>\d{{1,3}}|[IVXLCDM]{{1,6}})\.?\s*(?P<title>.{{0,{_MAX_TITLE_LEN}}})$"
)
_PART_KINDS = {"Part", "PART", "Часть", "ЧАСТЬ"}

# References / Bibliography — самостоятельный заголовок (без dot-leader).
_REFERENCES_HEADING_RE = re.compile(
    r"^(?:\d{1,2}\.?\s+)?"
    r"(?P<title>References|Bibliography|Литература|Список\s+литературы|Библиография)\s*$",
    re.IGNORECASE,
)

# Table of Contents / Оглавление как самостоятельный заголовок страницы.
_TOC_TITLE_RE = re.compile(
    r"^(?:Table\s+of\s+)?(?P<title>Contents|Оглавление|Содержание)\s*$",
    re.IGNORECASE,
)

# "Оторванный" номер главы — сам по себе на строке (см. docstring модуля).
_BARE_NUMBER_RE = re.compile(r"^\d{1,3}$")
_TITLE_CANDIDATE_RE = re.compile(r"^[A-ZА-ЯЁ][^\n]{1,80}$")
_BARE_NUMBER_LOOKAHEAD = 4  # сколько строк вперёд искать title после номера


@dataclass(slots=True)
class _Heading:
    level: int
    title: str
    start_offset: int
    zone: str | None = None
    # "bare_number" — эвристика "оторванный номер + строка-кандидат" ниже;
    # такие заголовки НЕ надёжны (см. _drop_repeated_running_headers) в
    # отличие от decimal/chapter/references/toc, у которых явный якорь.
    via: str = "pattern"


def _classify_line(
    line: str,
    lines: list[str],
    line_idx: int,
) -> _Heading | None:
    """Пытается распознать строку ``line`` (и, при "голом номере",
    заглядывает на несколько строк вперёд) как заголовок."""
    stripped = line.strip()
    if not stripped:
        return None

    # TOC/mini-TOC entry — не заголовок, независимо от того, что ещё matches.
    if _TOC_LINE_RE.match(stripped):
        return None

    if match := _DECIMAL_HEADING_RE.match(stripped):
        num = match.group("num")
        level = min(num.count(".") + 1, 4)
        # "N Title" без точки (просто "2 Title") неотличимо на уровне одной
        # строки от running header вида "<печатный номер страницы> <название
        # книги>", который повторяется почти на каждой странице (подтверждено
        # на реальном Handbook of Multisensor Data Fusion). "N.N Title" такой
        # проблеме не подвержен — у него есть подуровень, page header его не
        # имитирует. Поэтому bare "N Title" считается ненадёжным и попадает
        # под тот же repeated-title dedup, что и bare_number-эвристика ниже.
        via = "pattern" if "." in num else "bare_number"
        return _Heading(level=level, title=match.group("title").strip(), start_offset=-1, via=via)

    if match := _CHAPTER_HEADING_RE.match(stripped):
        level = 1 if match.group("kind") in _PART_KINDS else 2
        title = match.group("title").strip() or match.group("kind")
        return _Heading(level=level, title=title, start_offset=-1)

    if match := _REFERENCES_HEADING_RE.match(stripped):
        return _Heading(
            level=1, title=match.group("title").strip(), start_offset=-1, zone="references"
        )

    if match := _TOC_TITLE_RE.match(stripped):
        return _Heading(level=1, title=match.group("title").strip(), start_offset=-1, zone="toc")

    if _BARE_NUMBER_RE.match(stripped):
        for lookahead in range(1, _BARE_NUMBER_LOOKAHEAD + 1):
            j = line_idx + lookahead
            if j >= len(lines):
                break
            candidate = lines[j].strip()
            if not candidate:
                continue
            if _BARE_NUMBER_RE.match(candidate):
                continue  # повторный "декоративный" номер — пропускаем дальше.
            if (
                _TITLE_CANDIDATE_RE.match(candidate)
                and not _TOC_LINE_RE.match(candidate)
                and not _DECIMAL_HEADING_RE.match(candidate)
            ):
                return _Heading(level=1, title=candidate, start_offset=-1, via="bare_number")
            break  # первая содержательная строка после номера — не title-кандидат.

    return None


def _drop_repeated_running_headers(headings: list[_Heading]) -> list[_Heading]:
    """"Оторванный номер + title" ловит не только настоящие заголовки глав,
    но и running header/footer вида "<номер страницы>\\n<название книги>",
    который повторяется почти на каждой странице. Настоящие заголовки глав
    — уникальные строки, а running header — дословно повторяется много раз,
    так что дублирующиеся bare_number-заголовки безопасно отбросить.
    """
    counts = Counter(h.title for h in headings if h.via == "bare_number")
    repeated = {title for title, n in counts.items() if n > 1}
    return [h for h in headings if not (h.via == "bare_number" and h.title in repeated)]


def _split_with_offsets(body: str) -> tuple[list[str], list[int]]:
    lines = body.split("\n")
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return lines, offsets


def _page_for_offset(page_spans: list[tuple[int, int, int]], offset: int) -> int:
    """page_spans: [(page_number, start, end)]. Возвращает page_number,
    содержащий ``offset`` (или ближайший, если offset на границе)."""
    for page_number, start, end in page_spans:
        if start <= offset < end:
            return page_number
    return page_spans[-1][0] if page_spans else 1


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
            page_count = len(reader.pages)
        except DependencyError as exc:
            raise ParseFailedError(
                (f"PDF requires optional dependency for encryption (install pypdf[crypto]): {exc}"),
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            ) from exc
        except (PdfReadError, PyPdfError, Exception) as exc:
            raise ParseFailedError(
                f"PDF read error: {exc}",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            ) from exc

        if page_count == 0:
            raise ParseFailedError(
                "PDF has no pages",
                error_code="TEXT_EXTRACTION_FAILED",
                filename=filename,
            )

        pages: list[tuple[int, str]] = []
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except DependencyError as exc:
                raise ParseFailedError(
                    (f"PDF page extraction requires optional cryptography dependency: {exc}"),
                    error_code="TEXT_EXTRACTION_FAILED",
                    filename=filename,
                ) from exc
            except Exception as exc:  # noqa: BLE001 — pypdf бросает разные
                raise ParseFailedError(
                    f"PDF page {page_num} extraction error: {exc}",
                    error_code="TEXT_EXTRACTION_FAILED",
                    filename=filename,
                ) from exc
            page_text = page_text.strip()
            if page_text:
                pages.append((page_num, page_text))

        if not pages:
            # Все страницы пусты → scanned PDF без OCR.
            raise ParseFailedError(
                "PDF has no extractable text layer (likely scanned, OCR not supported)",
                error_code="PDF_TEXT_LAYER_NOT_FOUND",
                filename=filename,
            )

        # Конкатенируем все страницы в один body + запоминаем page spans,
        # чтобы находить page_number по смещению внутри body.
        body_parts: list[str] = []
        page_spans: list[tuple[int, int, int]] = []
        cursor = 0
        for page_num, page_text in pages:
            start = cursor
            body_parts.append(page_text)
            cursor += len(page_text)
            page_spans.append((page_num, start, cursor))
            cursor += 1  # delimiter "\n"
        body = "\n".join(body_parts)

        lines, line_offsets = _split_with_offsets(body)
        headings: list[_Heading] = []
        for idx, line in enumerate(lines):
            heading = _classify_line(line, lines, idx)
            if heading is not None:
                heading.start_offset = line_offsets[idx]
                headings.append(heading)
        headings = _drop_repeated_running_headers(headings)

        now = datetime.now(tz=UTC)

        if not headings:
            # Fallback: ни одного заголовка во всём документе — как раньше,
            # одна секция на страницу (T-S04-014 baseline).
            return self._pages_as_sections(pages, page_count, parse_job_id, source_document_id, now)

        sections: list[ParsedSection] = []
        path_stack: list[tuple[int, str]] = []

        def _emit(
            *,
            title: str,
            heading_path: list[str],
            start: int,
            end: int,
            zone: str | None,
        ) -> None:
            raw = body[start:end].strip()
            if not raw:
                return
            page_start = _page_for_offset(page_spans, start)
            page_end = _page_for_offset(page_spans, max(end - 1, start))
            structural: dict[str, object] = {
                "page_number": page_start,
                "page_start": page_start,
                "page_end": page_end,
            }
            if not sections:
                structural["page_count"] = page_count
            if zone is not None:
                structural["zone"] = zone
            sections.append(
                ParsedSection(
                    section_id=f"sec_{uuid.uuid4().hex[:12]}",
                    parse_job_id=parse_job_id,
                    source_document_id=source_document_id,
                    section_index=len(sections),
                    parent_section_id=None,
                    classification_method="rule_based",
                    heading_path=heading_path,
                    title=title,
                    section_type=SectionType.UNKNOWN,
                    raw_text=raw,
                    normalized_text=raw,
                    start_offset=start,
                    end_offset=end,
                    # zone-секции (toc/references) — не контент для карточек,
                    # заниженный confidence позволяет downstream отфильтровать
                    # их вместе с обычными low-confidence секциями.
                    confidence=0.3 if zone is not None else 0.75,
                    structural_payload=structural,
                    metadata={"page_number": page_start},
                    created_at=now,
                )
            )

        # Контент перед первым заголовком (титульная/копирайт страницы и т.п.).
        if headings[0].start_offset > 0:
            _emit(
                title="Front matter",
                heading_path=[],
                start=0,
                end=headings[0].start_offset,
                zone=None,
            )

        for i, heading in enumerate(headings):
            end = headings[i + 1].start_offset if i + 1 < len(headings) else len(body)
            path_stack = [(lvl, t) for lvl, t in path_stack if lvl < heading.level]
            heading_path = [t for _, t in path_stack]
            path_stack.append((heading.level, heading.title))
            _emit(
                title=heading.title,
                heading_path=heading_path,
                start=heading.start_offset,
                end=end,
                zone=heading.zone,
            )

        if not sections:
            # Все заголовки распознались, но ни одна секция не дала непустой
            # текст (вырожденный случай) — fallback на per-page.
            return self._pages_as_sections(pages, page_count, parse_job_id, source_document_id, now)

        return sections

    @staticmethod
    def _pages_as_sections(
        pages: list[tuple[int, str]],
        page_count: int,
        parse_job_id: str,
        source_document_id: str,
        now: datetime,
    ) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        cumulative_offset = 0
        for page_num, page_text in pages:
            structural: dict[str, object] = {"page_number": page_num}
            if page_num == pages[0][0]:
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
            cumulative_offset += len(page_text) + 1
        return sections
