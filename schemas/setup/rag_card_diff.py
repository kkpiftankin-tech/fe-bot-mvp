"""RAGCardDiffDTO (SETUP-06 / T-S06-004).

Сравнение двух версий RAG-карточки. Используется для UI diff view
(вкладка Diff в RAGCardReviewDrawer).

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §15.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MetadataFieldDiff(BaseModel):
    """Разница одного поля metadata между двумя версиями."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(..., min_length=1, max_length=128)
    old_value: Any = None
    new_value: Any = None


class BodyDiff(BaseModel):
    """Разница Markdown body. MVP — unified diff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["unified"] = "unified"
    content: str = Field(default="", max_length=200_000)


class RAGCardDiffDTO(BaseModel):
    """Diff между двумя версиями карточки.

    Если ``body_diff is None`` — тело не менялось.
    Если ``metadata_diff`` пустой — metadata не менялась.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(..., min_length=1)
    from_version: str = Field(..., pattern=r"^\d+\.\d+$")
    to_version: str = Field(..., pattern=r"^\d+\.\d+$")
    metadata_diff: list[MetadataFieldDiff] = Field(default_factory=list)
    body_diff: BodyDiff | None = None
