"""Unit-тесты импорта ASCII-дерева (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fe_bot.classifier.import_tree import (
    TreeImportError,
    counts_by_level,
    parse_ascii_tree,
)

pytestmark = pytest.mark.unit

_SOURCE_FILE = (
    Path(__file__).resolve().parents[2]
    / "incoming-docs"
    / "raw"
    / "Классификатор.md"
)

_SMALL_TREE = """\
АСУ/
├── Задача/
│   ├── Назначение/
│   │   ├── Цель управления
│   │   └── Объект управления
│   └── Контекст
└── Данные
"""


class TestParseAsciiTree:
    def test_small_tree_structure(self) -> None:
        tree = parse_ascii_tree(_SMALL_TREE)
        assert len(tree.root_ids) == 1
        root = tree.nodes[tree.root_ids[0]]
        assert root.name == "АСУ"
        assert len(root.children_ids) == 2  # Задача, Данные

        task = next(n for n in tree.nodes.values() if n.name == "Задача")
        assert task.level == 0
        assert task.is_leaf is False
        assert len(task.children_ids) == 2  # Назначение, Контекст

        purpose = next(n for n in tree.nodes.values() if n.name == "Назначение")
        assert purpose.level == 1
        assert len(purpose.children_ids) == 2

        goal = next(n for n in tree.nodes.values() if n.name == "Цель управления")
        assert goal.level == 2
        assert goal.is_leaf is True

        data = next(n for n in tree.nodes.values() if n.name == "Данные")
        assert data.level == 0
        assert data.is_leaf is True

    def test_get_path_roundtrip(self) -> None:
        tree = parse_ascii_tree(_SMALL_TREE)
        goal = next(n for n in tree.nodes.values() if n.name == "Цель управления")
        assert tree.get_path(goal.node_id) == [
            "АСУ",
            "Задача",
            "Назначение",
            "Цель управления",
        ]

    def test_duplicate_names_get_distinct_node_ids(self) -> None:
        text = """\
АСУ/
├── A/
│   └── X
└── B/
    └── X
"""
        tree = parse_ascii_tree(text)
        xs = [n for n in tree.nodes.values() if n.name == "X"]
        assert len(xs) == 2
        assert xs[0].node_id != xs[1].node_id

    def test_skipped_indentation_level_raises(self) -> None:
        # Прыжок с level 0 сразу на level 2 (пропущен level 1) — malformed.
        text = "АСУ/\n├── A/\n│   │   ├── B\n"
        with pytest.raises(TreeImportError):
            parse_ascii_tree(text)

    def test_empty_text_raises(self) -> None:
        with pytest.raises(TreeImportError):
            parse_ascii_tree("")


class TestRealClassifierDocument:
    """Проверка на реальном файле — см. Классификатор.md: заявлено
    12 → 64 → 336 → 345 → 122 → 27 узлов по уровням, 906 всего."""

    @pytest.fixture(scope="class")
    def tree_text(self) -> str:
        if not _SOURCE_FILE.exists():
            pytest.skip(f"{_SOURCE_FILE} not present")
        full_text = _SOURCE_FILE.read_text(encoding="utf-8")
        match = re.search(r"```text\n(.*?)```", full_text, re.DOTALL)
        assert match is not None, "No ```text fenced tree block found"
        return match.group(1)

    def test_level_counts_match_documented_shape(self, tree_text: str) -> None:
        tree = parse_ascii_tree(tree_text)
        counts = counts_by_level(tree)
        assert counts == {0: 12, 1: 64, 2: 336, 3: 345, 4: 122, 5: 27}
        assert sum(counts.values()) == 906

    def test_every_non_leaf_node_has_children(self, tree_text: str) -> None:
        tree = parse_ascii_tree(tree_text)
        for node in tree.nodes.values():
            if not node.is_leaf:
                assert len(node.children_ids) > 0
