"""Общий slugify для node_id (SETUP-13). Используется import_tree.py и
tree_service.py — вынесено, чтобы не дублировать логику."""

from __future__ import annotations

import re

# node_id возвращается LLM в JSON ("selected_child_id") — должен быть
# латиницей/ASCII, а не кириллицей: так классификатору и разработчикам,
# читающим логи/трейсы, не нужно гадать точное написание кириллического
# токена. Практическая (не строго ГОСТ) таблица транслитерации,
# распространённая в веб-slug-генераторах.
_CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _transliterate(text: str) -> str:
    return "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in text.lower())


def slugify(name: str, existing_ids: set[str]) -> str:
    """Стабильный, человекочитаемый ASCII node_id из имени узла.

    Не мутирует ``existing_ids`` — вызывающий сам решает, когда
    регистрировать возвращённый id (см. import_tree.py, где id нужно
    сразу добавить в общий seen-set по мере обхода дерева).
    """
    base = re.sub(r"[^a-z0-9]+", "_", _transliterate(name)).strip("_") or "node"
    base = base[:48]
    candidate = base
    n = 1
    while candidate in existing_ids:
        n += 1
        candidate = f"{base}_{n}"
    return candidate
