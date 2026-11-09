"""DTOs для Classifier Library API (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClassifierNodeDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    parent_id: str | None
    level: int
    name: str
    description: str
    children_ids: list[str]
    prompt_override: str | None
    is_leaf: bool
    path: list[str] = Field(default_factory=list)


class ClassifierNodeDetailsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: ClassifierNodeDTO
    children: list[ClassifierNodeDTO]
    rendered_prompt: str | None = Field(
        default=None, description="None если у узла нет детей (нечего классифицировать)."
    )


class ClassifierTreeSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tree_id: str
    version: str
    description: str
    total_nodes: int
    roots: list[ClassifierNodeDTO]


class CreateChildNodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2048)


class UpdateNodeRequest(BaseModel):
    """Все поля опциональны — переданы только те, что нужно изменить.

    ``prompt_override``: чтобы явно СБРОСИТЬ на общий шаблон, передай
    ``"__clear__"`` (JSON ``null`` неотличим от «поле не передано» в
    optional-теле FastAPI без разделения на два поля).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2048)
    prompt_override: str | None = Field(default=None, max_length=8192)
    clear_prompt_override: bool = Field(default=False)


class DeleteNodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    deleted_count: int
    message: str


class GenerateDescriptionResponse(BaseModel):
    """Черновик описания от маленькой LLM — не сохраняется автоматически,
    сохраняется через обычный PATCH после review пользователем."""

    model_config = ConfigDict(extra="forbid")

    description: str
