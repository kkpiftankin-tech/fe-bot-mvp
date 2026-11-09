"""Unit-тесты slugify (SETUP-13 / ADR-HTC-09) — node_id должен быть ASCII,
так как его же возвращает LLM в JSON ("selected_child_id")."""

from __future__ import annotations

import pytest

from fe_bot.classifier.slug import slugify

pytestmark = pytest.mark.unit


class TestSlugify:
    def test_transliterates_cyrillic_name(self) -> None:
        assert slugify("Аналитика", set()) == "analitika"

    def test_transliterates_multiword_name(self) -> None:
        assert slugify("Моделирование", set()) == "modelirovanie"

    def test_latin_name_stays_lowercase_ascii(self) -> None:
        assert slugify("DNN", set()) == "dnn"

    def test_result_is_ascii_only(self) -> None:
        for name in ["Оценивание", "Ситуационная осведомлённость", "JDL-5", "DNN/CNN"]:
            assert slugify(name, set()).isascii()

    def test_deduplicates_against_existing_ids(self) -> None:
        first = slugify("Задача", set())
        second = slugify("Задача", {first})
        assert first != second
        assert second == f"{first}_2"

    def test_empty_or_symbol_only_name_falls_back_to_node(self) -> None:
        assert slugify("---", set()) == "node"
