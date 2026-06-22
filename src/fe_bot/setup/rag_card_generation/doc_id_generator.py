"""DocIdGenerator (SETUP-05 / T-S05-017).

Деterministic генерация ``doc_id`` для RAG-карточки.

Формат: ``{doc_type_short}.{slug(title)}.v{N}``

Compatible:
- doc_type_short — короткое имя без суффикса ``_card`` (schema, task, analytics,
  field, pattern, validation, question).
- slug(title) — lower + ASCII transliteration кириллицы + non-alnum → ``_`` +
  truncate до 50 символов.
- При конфликте с ``existing_doc_ids`` инкрементируем ``vN`` (v1 → v2 → v3).

API:
- ``generate_doc_id(doc_type, title, *, existing_doc_ids)`` — возвращает уникальный
  ``doc_id``. Если slug пустой (после очистки от не-alphanumeric), возвращает
  ``{short}.unnamed.v1`` (с conflict resolution через vN).
"""

from __future__ import annotations

import re

_DOC_TYPE_SHORT: dict[str, str] = {
    "schema_card": "schema",
    "task_card": "task",
    "analytics_card": "analytics",
    "field_definition_card": "field",
    "feature_pattern_card": "pattern",
    "validation_rule_card": "validation",
    "question_template_card": "question",
}

_MAX_SLUG_LEN = 50
_VERSION_PATTERN = re.compile(r"^(.+)\.v(\d+)$")

# Простой transliteration map (cyrillic → latin).
_TRANSLIT: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


class UnsupportedDocTypeForId(ValueError):
    def __init__(self, doc_type: str) -> None:
        self.doc_type = doc_type
        super().__init__(f"Unsupported doc_type for ID generation: {doc_type!r}")


def _transliterate(text: str) -> str:
    out_chars: list[str] = []
    for ch in text.lower():
        if ch in _TRANSLIT:
            out_chars.append(_TRANSLIT[ch])
        else:
            out_chars.append(ch)
    return "".join(out_chars)


def _slug(title: str) -> str:
    """Lowercase + transliterate + replace non-alnum с ``_`` + truncate."""
    text = _transliterate(title)
    # Replace anything that's not alnum (ASCII) with ``_``.
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    if not text:
        return "unnamed"
    return text[:_MAX_SLUG_LEN].rstrip("_")


class DocIdGenerator:
    """Stateless генератор doc_id с conflict resolution через version bump."""

    def generate_doc_id(
        self,
        doc_type: str,
        title: str,
        *,
        existing_doc_ids: set[str],
    ) -> str:
        if doc_type not in _DOC_TYPE_SHORT:
            raise UnsupportedDocTypeForId(doc_type)
        short = _DOC_TYPE_SHORT[doc_type]
        slug = _slug(title)
        base = f"{short}.{slug}"

        # Найти все существующие версии в формате base.vN.
        # Bumping начинается с v1; если v1 уже занят — v2, и т.д.
        used_versions: set[int] = set()
        for did in existing_doc_ids:
            match = _VERSION_PATTERN.match(did)
            if match is None:
                continue
            if match.group(1) != base:
                continue
            try:
                used_versions.add(int(match.group(2)))
            except ValueError:
                continue

        next_version = 1
        while next_version in used_versions:
            next_version += 1
        return f"{base}.v{next_version}"
