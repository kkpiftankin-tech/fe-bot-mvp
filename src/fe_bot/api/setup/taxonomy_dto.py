"""DTOs для taxonomy API (SETUP-12 / T-S12-070).

Read-only представления реестра для frontend'а:
- ``TaxonomyVersionDTO`` — метаданные активной версии.
- ``TaxonomyNodeDTO`` — один класс уровня с display_name + статистикой.
- ``TaxonomyTreeNodeDTO`` — узел дерева с children (recursive).
- ``TaxonomyTreeResponse`` — полное дерево активной версии.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaxonomyVersionDTO(BaseModel):
    """Метаданные версии (without entries)."""

    model_config = ConfigDict(extra="forbid")

    version_id: str
    created_at: datetime
    description: str = ""
    is_active: bool


class TaxonomyNodeDTO(BaseModel):
    """Один класс таксономии в плоском виде."""

    model_config = ConfigDict(extra="forbid")

    version_id: str
    level: int = Field(..., ge=0, le=2)
    parent_path: str
    bit_index: int = Field(..., ge=0, le=9)
    class_slug: str
    display_name_ru: str
    display_name_en: str = ""
    description: str
    doc_type_hint: str | None
    auto_created: bool
    usage_count: int


class TaxonomyTreeNodeDTO(BaseModel):
    """Дерево: узел + список детей.

    children отсортированы по bit_index.
    """

    model_config = ConfigDict(extra="forbid")

    node: TaxonomyNodeDTO
    children: list[TaxonomyTreeNodeDTO] = Field(default_factory=list)


class TaxonomyTreeResponse(BaseModel):
    """Корневой ответ для GET /taxonomy/tree."""

    model_config = ConfigDict(extra="forbid")

    version: TaxonomyVersionDTO
    roots: list[TaxonomyTreeNodeDTO] = Field(default_factory=list)
    total_classes: int = Field(..., ge=0)
    auto_created_count: int = Field(..., ge=0)


class TaxonomyVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versions: list[TaxonomyVersionDTO] = Field(default_factory=list)
    active_version_id: str | None = None
