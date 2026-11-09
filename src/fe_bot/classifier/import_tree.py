"""Импорт ASCII-дерева (box-drawing, ``├──``/``└──``) в ClassifierTree.

SETUP-13 / ADR-HTC-09. Источник: ``incoming-docs/raw/Классификатор.md``
(и любой документ в том же формате — Unicode box-drawing, отступ 4
символа на уровень, узлы с детьми помечены завершающим ``/``).
"""

from __future__ import annotations

import re
import uuid

from schemas.classifier.node import ClassifierNode
from schemas.classifier.tree import ClassifierTree

from fe_bot.classifier.slug import slugify

_CONNECTOR_RE = re.compile(r"(├── |└── )")


class TreeImportError(ValueError):
    """Малформленный ASCII-текст дерева (несогласованные отступы и т.п.)."""


def _slugify(name: str, seen: set[str]) -> str:
    """Как ``slugify``, но сразу регистрирует id в ``seen`` — удобно при
    последовательном обходе дерева построчно."""
    candidate = slugify(name, seen)
    seen.add(candidate)
    return candidate


def parse_ascii_tree(text: str, *, root_name: str = "АСУ") -> ClassifierTree:
    """Парсит блок ```text ...``` с ASCII-деревом в ``ClassifierTree``.

    Корень (``root_name``) не считается уровнем — первая строка вида
    ``root_name/`` пропускается, её прямые дети получают ``level=0``.
    """
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("```")
    ]
    if not lines:
        raise TreeImportError("Empty tree text")

    seen_ids: set[str] = set()
    root_id = _slugify(root_name, seen_ids)
    root_node = ClassifierNode(
        node_id=root_id, parent_id=None, level=-1, name=root_name, children_ids=[]
    )
    nodes: dict[str, ClassifierNode] = {root_id: root_node}
    # Стек (level, node_id) — level здесь считается от 0 (дети корня).
    stack: list[tuple[int, str]] = [(-1, root_id)]

    first_line = lines[0].strip()
    if first_line in {f"{root_name}/", root_name}:
        lines = lines[1:]

    for raw_line in lines:
        match = _CONNECTOR_RE.search(raw_line)
        if match is None:
            continue
        prefix = raw_line[: match.start()]
        if len(prefix) % 4 != 0:
            raise TreeImportError(f"Malformed indentation: {raw_line!r}")
        level = len(prefix) // 4
        name_part = raw_line[match.end() :].rstrip()
        has_children = name_part.endswith("/")
        name = name_part[:-1] if has_children else name_part
        if not name:
            raise TreeImportError(f"Empty node name: {raw_line!r}")

        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack:
            raise TreeImportError(f"No parent found for line: {raw_line!r}")
        parent_level, parent_id = stack[-1]
        if parent_level != level - 1:
            raise TreeImportError(
                f"Indentation skip (parent level {parent_level}, node level "
                f"{level}) at: {raw_line!r}"
            )

        node_id = _slugify(name, seen_ids)
        node = ClassifierNode(
            node_id=node_id,
            parent_id=parent_id,
            level=level,
            name=name,
            children_ids=[],
        )
        nodes[node_id] = node
        nodes[parent_id] = nodes[parent_id].model_copy(
            update={"children_ids": [*nodes[parent_id].children_ids, node_id]}
        )
        stack.append((level, node_id))

    return ClassifierTree(
        tree_id=f"classifier_{uuid.uuid4().hex[:12]}",
        nodes=nodes,
        root_ids=[root_id],
    )


def counts_by_level(tree: ClassifierTree) -> dict[int, int]:
    """Число узлов на каждом уровне (не считая корень, level=-1)."""
    counts: dict[int, int] = {}
    for node in tree.nodes.values():
        if node.level < 0:
            continue
        counts[node.level] = counts.get(node.level, 0) + 1
    return counts
