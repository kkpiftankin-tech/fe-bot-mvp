"""MarkdownBuilder (SETUP-05 / T-S05-020).

Собирает финальный Markdown карточки из ``RAGCardMetadataDTO`` (YAML front matter)
и body. Применяет sanitization к body для защиты от prompt-injection-like span'ов
и небезопасного HTML.

Также предоставляет ``extract_front_matter()`` для обратной операции (парсинг).
"""

from __future__ import annotations

import io
import re

import yaml
from schemas.setup.rag_card_markdown import RAGCardMarkdownDTO
from schemas.setup.rag_card_metadata import RAGCardMetadataDTO

# Order для deterministic YAML serialization (required first, optional after).
_DETERMINISTIC_KEY_ORDER = (
    "doc_id",
    "doc_type",
    "title",
    "version",
    "status",
    "source_files",
    "source_sections",
    "domain",
    "phase",
    "retrieval_tags",
    "task_type",
    "data_source",
    "entity_type",
    "agent_targets",
    "required_input_fields",
    "output_fields",
    "feature_tables",
    "validation_rules",
    "compatible_models",
    "owner",
    "last_verified_at",
    "metadata_schema_version",
)

# Regex'ы для sanitization тела markdown.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_DANGEROUS_TAG_RE = re.compile(
    r"<\s*(script|iframe|style|object|embed|link|meta)\b[^>]*?>.*?<\s*/\s*\1\s*>",
    re.DOTALL | re.IGNORECASE,
)
_SELF_CLOSING_DANGEROUS_RE = re.compile(
    r"<\s*(script|iframe|style|object|embed|link|meta)\b[^>]*?/?>",
    re.IGNORECASE,
)
_SYSTEM_PROMPT_LINE_RE = re.compile(
    r"^\s*(system\s*:|assistant\s*:|<\s*system\s*>|<\s*\|im_start\s*\|>)",
    re.IGNORECASE | re.MULTILINE,
)


def _ordered_front_matter(front_matter: dict[str, object]) -> dict[str, object]:
    """Сортирует ключи по _DETERMINISTIC_KEY_ORDER; неизвестные — alphabetically в конец."""
    known = [k for k in _DETERMINISTIC_KEY_ORDER if k in front_matter]
    unknown = sorted(k for k in front_matter if k not in _DETERMINISTIC_KEY_ORDER)
    return {k: front_matter[k] for k in (*known, *unknown)}


def sanitize_body(body: str) -> str:
    """Удаляет HTML-комментарии, dangerous tags, prompt-injection-like префиксы.

    Markdown-форматирование (заголовки, списки) сохраняется.
    """
    out = body

    # HTML-комментарии.
    out = _HTML_COMMENT_RE.sub("", out)

    # Парные dangerous tags.
    out = _DANGEROUS_TAG_RE.sub("", out)

    # Self-closing dangerous tags (<script .../>, <iframe ...>).
    out = _SELF_CLOSING_DANGEROUS_RE.sub("", out)

    # Префиксы system:/assistant:/<|im_start|>.
    out = _SYSTEM_PROMPT_LINE_RE.sub("", out)

    # Нормализуем CRLF → LF.
    out = out.replace("\r\n", "\n").replace("\r", "\n")

    return out.strip("\n") + "\n"


def render_front_matter(metadata: RAGCardMetadataDTO) -> str:
    """Сериализует RAGCardMetadataDTO.front_matter в YAML (deterministic order)."""
    ordered = _ordered_front_matter(metadata.front_matter)
    # metadata_schema_version всегда присутствует.
    ordered.setdefault("metadata_schema_version", metadata.metadata_schema_version)
    buf = io.StringIO()
    yaml.safe_dump(
        ordered,
        buf,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    return buf.getvalue().rstrip("\n")


def build_markdown(
    metadata: RAGCardMetadataDTO,
    body_markdown: str,
) -> RAGCardMarkdownDTO:
    """Собирает финальный Markdown DTO: front matter + sanitized body."""
    yaml_text = render_front_matter(metadata)
    body_clean = sanitize_body(body_markdown)
    return RAGCardMarkdownDTO.from_parts(
        doc_id=metadata.doc_id,
        card_version=metadata.card_version,
        front_matter_yaml=yaml_text,
        body_markdown=body_clean,
    )


def extract_front_matter(markdown: str) -> tuple[dict[str, object], str]:
    """Обратная операция: parse RAG-карточку Markdown в (front_matter_dict, body).

    Raises:
        ValueError: если delimiter '---\\n' отсутствует или невалидный YAML.
    """
    if not markdown.startswith("---\n"):
        raise ValueError("markdown must start with '---\\n' front matter delimiter")
    parts = markdown.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError("markdown must contain closing '---\\n' front matter delimiter")
    fm_text = parts[1]
    body = parts[2].lstrip("\n")
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in front matter: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("YAML front matter must be a mapping")
    return data, body
