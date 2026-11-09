"""SectionLengthNormalizer (SETUP-04).

Пост-обработка списка ``ParsedSection``, полученного от ``ParserStrategy``,
ПЕРЕД классификацией (``Orchestrator`` вызывает это между ``strategy.parse()``
и ``classifier.apply_to_sections()``). Не меняет boundary-детекцию стратегий
(заголовки/нумерацию) — работает над уже извлечёнными секциями:

- Слишком короткие секции (``len(raw_text) < min_chars``) объединяются
  СОСЕДНИМИ, только если заголовок каждой из них сам похож на пункт
  нумерованного списка (``_LIST_ITEM_TITLE_RE``: "1. ...", "2 ...") —
  именно та форма, которую ``_DECIMAL_HEADING_RE`` в PDF-парсере путает с
  настоящим заголовком. Секция с обычным заголовком (``# Introduction``,
  ``# A``) никогда не объединяется — независимо от длины: короткая, но
  самостоятельная секция (термин глоссария, короткое поле схемы) не
  теряет идентичность только из-за объёма текста. Среди подряд идущих
  «похожих на список» секций объединение дополнительно требует совпадения
  ``(heading_path, parent_section_id)`` — не сливает через границу
  настоящего заголовка, даже если оба соседа сами выглядят как пункты
  списка. Если после объединения вперёд остаток рана всё равно короче
  ``min_chars`` (последняя секция рана), объединяется НАЗАД с предыдущим
  уже собранным куском — секция остаётся короче порога только если она
  единственная в своём ране (больше не с чем объединять).
- Слишком длинные секции (``len(raw_text) > max_chars``) делятся по границам
  абзацев (``\\n\\s*\\n``) на несколько секций с тем же ``heading_path`` —
  никогда не режет абзац посередине. Если один абзац сам длиннее
  ``max_chars``, он остаётся отдельной (длинной) секцией как есть.

Причина появления этого модуля — PDF-документы, где `_DECIMAL_HEADING_RE`
(см. ``strategies/pdf_parser.py``) ложно принимает пункты нумерованного
списка за заголовки: каждый пункт становится отдельной секцией, а длина
секции — это сколько текста автор документа написал под конкретным
пунктом, что даёт разброс от десятков до тысяч символов без всякого
отношения к тому, сколько текста разумно поместить в одну RAG-карточку.
"""

from __future__ import annotations

import re

from schemas.setup.parsed_section import ParsedSection

DEFAULT_MIN_CHARS = 800
DEFAULT_MAX_CHARS = 4000

_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"[ \t]+")

# Та же форма заголовка, которую _DECIMAL_HEADING_RE (pdf_parser.py) путает
# с настоящим заголовком: цифра(ы) + опциональная точка + пробел + текст.
# Намеренно НЕ импортируем _DECIMAL_HEADING_RE оттуда — это PDF-специфичная
# деталь строго структурного заголовка ("1.2 Title"), а здесь нужен более
# широкий сигнал "похоже на элемент перечисления", применимый к ЛЮБОЙ
# секции независимо от того, какая стратегия её произвела.
#
# Проверяем ПЕРВУЮ СТРОКУ raw_text, а не ``section.title``: ParserStrategy
# (см. pdf_parser.py ``_classify_line``) при распознавании нумерации уже
# вырезает номер в отдельную группу и кладёт в ``title`` только текст
# ПОСЛЕ номера — сам номер остаётся только в исходном тексте секции.
_LIST_ITEM_TITLE_RE = re.compile(r"^\d{1,3}\.?\s+\S")


def _looks_like_list_item(section: ParsedSection) -> bool:
    first_line = section.raw_text.lstrip().split("\n", 1)[0]
    return bool(_LIST_ITEM_TITLE_RE.match(first_line))


def _simple_normalize(text: str) -> str:
    """Normalized_text синтетических секций: collapsed whitespace + strip —
    та же трактовка поля, что в докстринге ``ParsedSection.normalized_text``.
    Не воспроизводит normalization конкретной ParserStrategy (markdown
    lower-casing и т.п.) — она не нужна downstream (классификация читает
    ``normalized_text or raw_text``, оба варианта приемлемы)."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _group_key(section: ParsedSection) -> tuple[tuple[str, ...], str | None]:
    return (tuple(section.heading_path), section.parent_section_id)


class SectionLengthNormalizer:
    """Объединяет слишком короткие и делит слишком длинные секции.

    Thresholds подобраны так, чтобы секция была самостоятельной единицей
    смысла для одной RAG-карточки (SETUP-05): не обрывок предложения,
    но и не произвольно большой кусок документа.
    """

    def __init__(
        self,
        *,
        min_chars: int = DEFAULT_MIN_CHARS,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        if min_chars <= 0:
            raise ValueError("min_chars must be > 0")
        if max_chars <= min_chars:
            raise ValueError("max_chars must be > min_chars")
        self._min = min_chars
        self._max = max_chars

    def normalize(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        if not sections:
            return sections
        merged = self._merge_short(sections)
        split = self._split_long(merged)
        return self._reindex(split)

    # ------------------------------------------------------------------
    # Merge too-short sections forward (fallback: backward at group tail)
    # ------------------------------------------------------------------

    def _merge_short(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        result: list[ParsedSection] = []
        run: list[ParsedSection] = []
        run_key: tuple[tuple[str, ...], str | None] | None = None

        def flush_run() -> None:
            if not run:
                return
            result.extend(self._merge_group(run) if len(run) > 1 else run)

        for section in sections:
            if not _looks_like_list_item(section):
                flush_run()
                run.clear()
                run_key = None
                result.append(section)
                continue
            key = _group_key(section)
            if run and key != run_key:
                flush_run()
                run.clear()
            run.append(section)
            run_key = key
        flush_run()
        return result

    def _merge_group(self, group: list[ParsedSection]) -> list[ParsedSection]:
        pieces: list[ParsedSection] = []
        acc: list[ParsedSection] = []

        def flush_acc() -> ParsedSection | None:
            if not acc:
                return None
            merged = acc[0] if len(acc) == 1 else self._combine(acc)
            acc.clear()
            return merged

        for section in group:
            acc.append(section)
            total_len = sum(len(s.raw_text) for s in acc)
            if total_len >= self._min:
                flushed = flush_acc()
                if flushed is not None:
                    pieces.append(flushed)

        # Остаток группы короче min_chars — объединяем назад в последний
        # собранный кусок (если есть), иначе оставляем единственным куском
        # группы как есть (больше не с чем объединять).
        if acc:
            if pieces:
                pieces[-1] = self._combine([pieces[-1], *acc])
            else:
                pieces.append(self._combine(acc) if len(acc) > 1 else acc[0])
            acc.clear()

        return pieces

    def _combine(self, parts: list[ParsedSection]) -> ParsedSection:
        # parts может включать уже смерженный кусок (backward-merge остатка
        # рана в предыдущий pieces[-1]) — тогда его собственный
        # length_normalizer_merged_from нужно разворачивать транзитивно,
        # иначе audit trail потеряет id'шники из вложенного merge'а (сам
        # raw_text при этом не теряется — он уже содержит их текст).
        def _source_ids(p: ParsedSection) -> list[str]:
            nested = p.metadata.get("length_normalizer_merged_from")
            return list(nested) if nested else [p.section_id]

        first = parts[0]
        raw_text = "\n\n".join(p.raw_text for p in parts)
        starts = [p.start_offset for p in parts if p.start_offset is not None]
        ends = [p.end_offset for p in parts if p.end_offset is not None]
        merged_from = [sid for p in parts for sid in _source_ids(p)]
        return ParsedSection(
            section_id=first.section_id,
            parse_job_id=first.parse_job_id,
            source_document_id=first.source_document_id,
            section_index=first.section_index,
            parent_section_id=first.parent_section_id,
            heading_path=first.heading_path,
            title=first.title,
            section_type=first.section_type,
            section_status=first.section_status,
            classification_method=first.classification_method,
            raw_text=raw_text,
            normalized_text=_simple_normalize(raw_text),
            start_offset=min(starts) if starts else None,
            end_offset=max(ends) if ends else None,
            confidence=min(p.confidence for p in parts),
            structural_payload=first.structural_payload,
            created_at=min(p.created_at for p in parts),
            metadata={
                **{k: v for k, v in first.metadata.items() if k != "length_normalizer_merged_from"},
                "length_normalizer_merged_from": merged_from,
            },
        )

    # ------------------------------------------------------------------
    # Split too-long sections at paragraph boundaries
    # ------------------------------------------------------------------

    def _split_long(self, sections: list[ParsedSection]) -> list[ParsedSection]:
        result: list[ParsedSection] = []
        for section in sections:
            if len(section.raw_text) <= self._max:
                result.append(section)
                continue
            result.extend(self._split_one(section))
        return result

    def _split_one(self, section: ParsedSection) -> list[ParsedSection]:
        paragraphs = [p for p in _PARAGRAPH_SPLIT_RE.split(section.raw_text) if p.strip()]
        if len(paragraphs) <= 1:
            return [section]  # один (длинный) абзац — не режем середину абзаца

        packed: list[str] = []
        current = ""
        for para in paragraphs:
            candidate = f"{current}\n\n{para}" if current else para
            if len(candidate) <= self._max or not current:
                current = candidate
            else:
                packed.append(current)
                current = para
        if current:
            packed.append(current)
        if len(packed) <= 1:
            return [section]

        text = section.raw_text
        cursor = 0
        pieces: list[ParsedSection] = []
        base_offset = section.start_offset or 0
        for idx, piece_text in enumerate(packed):
            found = text.index(piece_text, cursor)
            piece_start = base_offset + found
            piece_end = piece_start + len(piece_text)
            cursor = found + len(piece_text)
            pieces.append(
                ParsedSection(
                    section_id=(
                        section.section_id if idx == 0 else f"{section.section_id}_p{idx + 1}"
                    ),
                    parse_job_id=section.parse_job_id,
                    source_document_id=section.source_document_id,
                    section_index=section.section_index,
                    parent_section_id=section.parent_section_id,
                    heading_path=section.heading_path,
                    title=section.title if idx == 0 else f"{section.title} (часть {idx + 1})",
                    section_type=section.section_type,
                    section_status=section.section_status,
                    classification_method=section.classification_method,
                    raw_text=piece_text,
                    normalized_text=_simple_normalize(piece_text),
                    start_offset=piece_start if section.start_offset is not None else None,
                    end_offset=piece_end if section.end_offset is not None else None,
                    confidence=section.confidence,
                    structural_payload=section.structural_payload if idx == 0 else {},
                    created_at=section.created_at,
                    metadata={
                        **(section.metadata if idx == 0 else {}),
                        "length_normalizer_split_from": section.section_id,
                        "length_normalizer_part": idx + 1,
                        "length_normalizer_parts_total": len(packed),
                    },
                )
            )
        return pieces

    # ------------------------------------------------------------------

    @staticmethod
    def _reindex(sections: list[ParsedSection]) -> list[ParsedSection]:
        return [
            s.model_copy(update={"section_index": i}) if s.section_index != i else s
            for i, s in enumerate(sections)
        ]
