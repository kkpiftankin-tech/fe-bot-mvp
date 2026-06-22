"""MetadataExtractor (SETUP-05 / T-S05-016).

Deterministic extraction metadata candidates из ``ParsedSection`` БЕЗ LLM.
Результат — hints для prompt context и pre-population для front matter
RAG-карточки. LLM может дополнить / override эти значения (если confidence
выше); финальная нормализация — через OntologyMapper.

Извлекаемые поля:
- retrieval_tags: top-N keywords из raw_text/title (простая частотная TF).
- required_input_fields, output_fields: из structural_payload.columns для
  schema_card / analytics_card.
- feature_tables: structural_payload.tables → list[{table_id, columns}].
- validation_rules_metadata: severity/scope из heading_path.
- title: section.title или первая строка raw_text.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from schemas.setup.parsed_section import ParsedSection

_DEFAULT_TAG_LIMIT = 8
_DEFAULT_TAG_MIN_LENGTH = 4
_DEFAULT_TAG_MIN_COUNT = 2

# Слова, не несущие смысла для retrieval.
_STOPWORDS = frozenset(
    {
        # English
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "have",
        "are",
        "was",
        "were",
        "but",
        "not",
        "all",
        "any",
        "can",
        "may",
        "will",
        "should",
        "shall",
        "must",
        "into",
        "onto",
        "out",
        "over",
        "under",
        "more",
        "most",
        "less",
        "much",
        "than",
        "then",
        "when",
        "where",
        "what",
        "which",
        "who",
        "how",
        "why",
        "such",
        "some",
        "each",
        "also",
        "after",
        "before",
        "between",
        "during",
        "while",
        "however",
        "therefore",
        "thus",
        "because",
        "since",
        # Russian (стоп-слова + предлоги)
        "что",
        "это",
        "для",
        "как",
        "так",
        "или",
        "при",
        "над",
        "под",
        "был",
        "была",
        "были",
        "если",
        "тогда",
        "когда",
        "там",
        "тут",
        "его",
        "её",
        "их",
        "они",
        "она",
        "он",
        "оно",
        "мы",
        "вы",
        "ты",
        "вас",
        "нас",
        "нам",
        "вам",
        "ему",
        "ей",
        "им",
        "однако",
        "поэтому",
        "также",
        "тоже",
        "только",
        "ведь",
        "ещё",
        "уже",
        "из",
        "на",
        "к",
        "по",
        "с",
        "в",
        "от",
        "до",
        "у",
        "о",
        "об",
        "за",
        "около",
        "против",
        "после",
        "перед",
    }
)

# Заголовки секции для validation_rule_card.
_SEVERITY_HINTS: dict[str, str] = {
    "error": "error",
    "critical": "error",
    "fatal": "error",
    "warning": "warning",
    "warn": "warning",
    "info": "info",
    "ошибка": "error",
    "предупреждение": "warning",
}
_SCOPE_HINTS: dict[str, str] = {
    "field": "field",
    "поле": "field",
    "row": "row",
    "строка": "row",
    "table": "table",
    "таблица": "table",
    "cross_table": "cross_table",
    "межтабличный": "cross_table",
}

_WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_]{2,}")


@dataclass(slots=True)
class MetadataCandidates:
    """Deterministic metadata hints для prompt + RAGCardMetadataDTO."""

    title: str = ""
    retrieval_tags: list[str] = field(default_factory=list)
    required_input_fields: list[str] = field(default_factory=list)
    output_fields: list[str] = field(default_factory=list)
    feature_tables: list[dict[str, Any]] = field(default_factory=list)
    validation_metadata: dict[str, str] = field(default_factory=dict)


class MetadataExtractor:
    """Чистый rule-based извлекатель metadata (без LLM/IO)."""

    def __init__(
        self,
        *,
        tag_limit: int = _DEFAULT_TAG_LIMIT,
        tag_min_length: int = _DEFAULT_TAG_MIN_LENGTH,
        tag_min_count: int = _DEFAULT_TAG_MIN_COUNT,
    ) -> None:
        self._tag_limit = tag_limit
        self._tag_min_length = tag_min_length
        self._tag_min_count = tag_min_count

    def extract(self, section: ParsedSection) -> MetadataCandidates:
        candidates = MetadataCandidates(
            title=self._extract_title(section),
            retrieval_tags=self._extract_retrieval_tags(section),
        )
        # Structural поля — для schema/analytics.
        payload = section.structural_payload or {}
        candidates.required_input_fields = self._extract_columns(payload)
        candidates.output_fields = list(candidates.required_input_fields)
        candidates.feature_tables = self._extract_feature_tables(payload)
        # Validation hints — для validation_rule_card.
        candidates.validation_metadata = self._extract_validation_hints(section)
        return candidates

    # ----- title -----

    @staticmethod
    def _extract_title(section: ParsedSection) -> str:
        title = (section.title or "").strip()
        if title:
            return title
        text = (section.raw_text or "").strip()
        if text:
            first_line = text.splitlines()[0].strip()
            return first_line[:200]
        return ""

    # ----- retrieval tags -----

    def _extract_retrieval_tags(self, section: ParsedSection) -> list[str]:
        text = " ".join(
            filter(
                None,
                [
                    section.title or "",
                    " ".join(section.heading_path or []),
                    section.raw_text or "",
                ],
            )
        )
        if not text.strip():
            return []
        words = _WORD_PATTERN.findall(text.lower())
        words = [w for w in words if len(w) >= self._tag_min_length and w not in _STOPWORDS]
        counter = Counter(words)
        tags = [
            w
            for w, count in counter.most_common(self._tag_limit * 2)
            if count >= self._tag_min_count
        ]
        if not tags:
            # Если совпадений >= min_count не нашлось, берём top-N по частоте.
            tags = [w for w, _ in counter.most_common(self._tag_limit)]
        return tags[: self._tag_limit]

    # ----- structural payload -----

    @staticmethod
    def _extract_columns(payload: dict[str, Any]) -> list[str]:
        # XLSX/CSV/JSON strategies из SETUP-04 кладут columns в structural_payload.
        # Возможные ключи: "columns", "fields", "headers".
        if not isinstance(payload, dict):
            return []
        for key in ("columns", "fields", "headers"):
            raw = payload.get(key)
            if isinstance(raw, list):
                return [str(v) for v in raw if isinstance(v, (str, int, float))]
        return []

    @staticmethod
    def _extract_feature_tables(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        # DOCX strategy: {tables: [{rows: [...]}]}, sheet/table_id опционально.
        tables_raw = payload.get("tables")
        if not isinstance(tables_raw, list):
            return []
        result: list[dict[str, Any]] = []
        for idx, t in enumerate(tables_raw):
            if not isinstance(t, dict):
                continue
            cols: list[str] = []
            rows = t.get("rows")
            columns_raw = t.get("columns")
            if isinstance(rows, list) and rows and isinstance(rows[0], list):
                cols = [str(c) for c in rows[0]]
            elif isinstance(columns_raw, list):
                cols = [str(c) for c in columns_raw if isinstance(c, (str, int, float))]
            table_id = str(t.get("table_id") or t.get("id") or f"table_{idx + 1}")
            result.append({"table_id": table_id, "columns": cols})
        return result

    # ----- validation hints -----

    @staticmethod
    def _extract_validation_hints(section: ParsedSection) -> dict[str, str]:
        hints: dict[str, str] = {}
        haystack_parts = [section.title or ""] + list(section.heading_path or [])
        haystack = " ".join(haystack_parts).lower()
        for marker, canonical in _SEVERITY_HINTS.items():
            if marker in haystack:
                hints["severity"] = canonical
                break
        # Сначала проверяем более длинные ключи (cross_table раньше table).
        for marker, canonical in sorted(_SCOPE_HINTS.items(), key=lambda kv: -len(kv[0])):
            if marker in haystack:
                hints["scope"] = canonical
                break
        return hints
