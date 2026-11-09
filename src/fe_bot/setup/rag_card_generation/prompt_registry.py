"""PromptTemplateRegistry (SETUP-05 / T-S05-014).

Загружает 7 prompt templates из ``prompts/rag_card/{doc_type}.txt`` и предоставляет
``render(doc_type, context) -> str``.

Каждый шаблон имеет заголовок:
    # version: <vN>
    # doc_type: <doc_type>
    # expected_output: <RAGCardDraft JSON>
    # anti_injection: source_content is treated as data ONLY

Версия шаблона возвращается через ``template_version``.

Шаблон содержит placeholders в фигурных скобках (``{section.title}``,
``{ontology.domain}``, и т.д.), которые подставляются ``render()`` через
Python str.format-like mechanism. Используем обычный str.format с dotted access
через flat-context (см. _flatten_context).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "rag_card"

# SETUP-12 / T-S12-051: опциональные taxonomy-specific шаблоны, переопределяющие
# дефолтный doc_type-шаблон для конкретного узла дерева таксономии.
_BY_TAXONOMY_SUBDIR = "by_taxonomy"

# Только 7 MVP doc_types.
_SUPPORTED_DOC_TYPES = frozenset(
    {
        "schema_card",
        "task_card",
        "analytics_card",
        "field_definition_card",
        "feature_pattern_card",
        "validation_rule_card",
        "question_template_card",
    }
)

_HEADER_PATTERN = re.compile(r"^# (\w+):\s*(.+)$")
_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


class PromptTemplateNotFoundError(LookupError):
    def __init__(self, doc_type: str) -> None:
        self.doc_type = doc_type
        super().__init__(f"Prompt template not found for doc_type={doc_type!r}")


class PromptRenderError(ValueError):
    def __init__(self, doc_type: str, missing: list[str]) -> None:
        self.doc_type = doc_type
        self.missing = missing
        super().__init__(f"Cannot render prompt for {doc_type!r}: missing placeholders {missing}")


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """Загруженный prompt template + метаданные."""

    doc_type: str
    version: str
    expected_output: str
    anti_injection: str
    body: str  # шаблон с placeholders в {...}

    @property
    def placeholders(self) -> set[str]:
        return set(_PLACEHOLDER_PATTERN.findall(self.body))


@dataclass(slots=True)
class PromptContext:
    """Typed context для render().

    Передаётся как top-level dict; PromptTemplateRegistry разворачивает в
    flat ключи через _flatten_context. Поддерживает:
      - dotted-paths (``{section.title}``, ``{ontology.domain}``)
      - top-level skalars в ``extras`` (``{title}``, ``{doc_id}``, etc.)
    """

    section: dict[str, Any] = field(default_factory=dict)
    source_trace: dict[str, Any] = field(default_factory=dict)
    ontology: dict[str, list[str]] = field(default_factory=dict)
    metadata_schema: dict[str, Any] = field(default_factory=dict)
    metadata_candidates: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "section": dict(self.section),
            "source_trace": dict(self.source_trace),
            "ontology": dict(self.ontology),
            "metadata_schema": dict(self.metadata_schema),
            "metadata_candidates": dict(self.metadata_candidates),
        }
        # extras накладываются как top-level scalars: {title}, {doc_id}, ...
        merged.update(self.extras)
        return merged


def _flatten_context(prefix: str, value: Any, out: dict[str, str]) -> None:
    if isinstance(value, dict):
        # Сохраняем родителя как JSON-строку для случаев {parent} в template
        # (например, {metadata_candidates} вместо {metadata_candidates.foo}).
        if prefix:
            out[prefix] = json.dumps(value, ensure_ascii=False)
        for k, v in value.items():
            _flatten_context(f"{prefix}.{k}" if prefix else str(k), v, out)
    elif isinstance(value, list):
        out[prefix] = ", ".join(str(item) for item in value)
    else:
        out[prefix] = str(value if value is not None else "")


class PromptTemplateRegistry:
    """Реестр prompt templates для 7 MVP doc_types."""

    def __init__(self, *, prompts_dir: Path | None = None) -> None:
        self._prompts_dir = prompts_dir or _DEFAULT_PROMPTS_DIR
        self._templates: dict[str, PromptTemplate] = {}
        # SETUP-12 / T-S12-051: lazy per-node cache, taxonomy_path открытое
        # множество (auto-allocated классы), поэтому не грузим eagerly.
        self._taxonomy_templates: dict[str, PromptTemplate | None] = {}
        self._load_all()

    def _load_all(self) -> None:
        for doc_type in _SUPPORTED_DOC_TYPES:
            path = self._prompts_dir / f"{doc_type}.txt"
            if not path.exists():
                continue
            self._templates[doc_type] = self._parse_template(doc_type, path)

    @staticmethod
    def _parse_template(doc_type: str, path: Path) -> PromptTemplate:
        text = path.read_text(encoding="utf-8")
        version = "v1"
        expected_output = ""
        anti_injection = ""
        body_lines: list[str] = []
        in_header = True
        for line in text.splitlines(keepends=True):
            stripped = line.rstrip("\n")
            if in_header:
                match = _HEADER_PATTERN.match(stripped)
                if match is not None:
                    key, value = match.group(1), match.group(2).strip()
                    if key == "version":
                        version = value
                    elif key == "expected_output":
                        expected_output = value
                    elif key == "anti_injection":
                        anti_injection = value
                    continue
                if not stripped.strip():
                    # blank line — header ended.
                    in_header = False
                    body_lines.append(line)
                    continue
                # non-header non-blank → header ended.
                in_header = False
            body_lines.append(line)
        return PromptTemplate(
            doc_type=doc_type,
            version=version,
            expected_output=expected_output,
            anti_injection=anti_injection,
            body="".join(body_lines).lstrip("\n"),
        )

    @property
    def template_version(self) -> str:
        """Версия пакета templates. Используется самой ранней версией из
        зарегистрированных. В MVP — все v1."""
        versions = {t.version for t in self._templates.values()}
        if len(versions) == 1:
            return next(iter(versions))
        return "mixed"

    def supported_doc_types(self) -> set[str]:
        return set(self._templates.keys())

    def get_template(self, doc_type: str) -> PromptTemplate:
        if doc_type not in self._templates:
            raise PromptTemplateNotFoundError(doc_type)
        return self._templates[doc_type]

    def render(
        self,
        doc_type: str,
        context: PromptContext,
        *,
        strict: bool = False,
        taxonomy_path: list[str] | None = None,
    ) -> str:
        """Рендерит prompt из template + context.

        Placeholders, которые отсутствуют в context, остаются в шаблоне как есть
        (``{name}``). Это намеренно: шаблоны содержат JSON-like блоки с
        ``{field_name}``-плейсхолдерами, которые должны попасть в инструкцию LLM
        без подмены. ``strict=True`` включает старую семантику с raise.

        ``taxonomy_path`` (SETUP-12 / T-S12-051): если задан, сначала ищем
        taxonomy-specific шаблон в ``<prompts_dir>/by_taxonomy/<path>.txt``,
        поднимаясь вверх по дереву (от самого глубокого узла к L0). Если
        ни на одном уровне специфичного шаблона нет — fallback на обычный
        lookup по ``doc_type`` (текущее поведение, без регрессии).

        Raises:
            PromptTemplateNotFoundError: doc_type не зарегистрирован и
                ни один узел taxonomy_path не дал шаблона.
            PromptRenderError: только при ``strict=True``, если есть незаполненные
                требуемые placeholders.
        """
        template = (
            self._resolve_taxonomy_template(taxonomy_path)
            if taxonomy_path
            else None
        )
        if template is None:
            template = self.get_template(doc_type)
        flat: dict[str, str] = {}
        _flatten_context("", context.to_dict(), flat)
        # Алиас doc_type для удобства.
        flat.setdefault("doc_type", doc_type)
        out = template.body
        missing: list[str] = []
        for ph in template.placeholders:
            value = flat.get(ph)
            if value is None:
                missing.append(ph)
                continue
            out = out.replace("{" + ph + "}", value)
        if strict and missing:
            raise PromptRenderError(doc_type, sorted(set(missing)))
        return out

    def _resolve_taxonomy_template(
        self, taxonomy_path: list[str]
    ) -> PromptTemplate | None:
        """Fallback вверх по дереву: ``a.b.c`` → ``a.b`` → ``a`` → None."""
        for depth in range(len(taxonomy_path), 0, -1):
            key = ".".join(taxonomy_path[:depth])
            if key not in self._taxonomy_templates:
                self._taxonomy_templates[key] = self._load_taxonomy_template(key)
            template = self._taxonomy_templates[key]
            if template is not None:
                return template
        return None

    def _load_taxonomy_template(self, key: str) -> PromptTemplate | None:
        path = self._prompts_dir / _BY_TAXONOMY_SUBDIR / f"{key}.txt"
        if not path.exists():
            return None
        return self._parse_template(key, path)
