"""RAGCardVersionDTO (SETUP-06 / T-S06-003).

Версия RAG-карточки. Каждый manual edit создаёт новую minor version
(1.0 → 1.1); каждый regenerate — новую major (1.0 → 2.0). Старые версии
не удаляются.

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §15.3.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from schemas.rag.rag_card import CardStatus


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


def bump_version(version: str, *, bump_type: str = "minor") -> str:
    """Bump card_version.

    - ``bump_type="minor"``: 1.0 → 1.1, 1.5 → 1.6 (для edit).
    - ``bump_type="major"``: 1.0 → 2.0, 1.5 → 2.0 (для regenerate).

    Raises ValueError если version не соответствует формату ``N.N``.
    """
    match = _VERSION_RE.match(version)
    if match is None:
        raise ValueError(f"version {version!r} must match N.N format")
    major, minor = int(match.group(1)), int(match.group(2))
    if bump_type == "minor":
        return f"{major}.{minor + 1}"
    if bump_type == "major":
        return f"{major + 1}.0"
    raise ValueError(f"unknown bump_type {bump_type!r}; use 'minor' or 'major'")


class RAGCardVersionDTO(BaseModel):
    """Версия RAG-карточки.

    Уникальность: ``(doc_id, card_version)``. Только одна версия per doc_id
    с ``is_current=True``.

    Storage: PostgreSQL `rag_card_versions` (план); MVP — in-memory.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+\.\d+$")
    parent_card_version: str | None = Field(default=None, pattern=r"^\d+\.\d+$")
    status: CardStatus
    markdown_artifact_id: str = Field(..., min_length=1)
    metadata_snapshot: dict[str, Any] = Field(default_factory=dict)
    body_hash: str = Field(..., pattern=r"^sha256:[a-f0-9]{64}$")
    created_by: str = Field(..., min_length=1, max_length=128)
    created_at: datetime
    change_reason: str | None = Field(default=None, max_length=1000)
    is_current: bool = False
