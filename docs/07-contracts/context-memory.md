# Контракт ContextMemory

## Назначение

`ContextMemory` — типизированный объект состояния, который LangGraph передаёт между узлами. Один экземпляр на `conversation_id`; в БД хранятся per-phase снапшоты.

## Минимальная Pydantic-схема

```python
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

Phase = Literal[
    "initialization", "task_discovery", "data_profiling", "domain_context",
    "feature_synthesis", "data_generation", "model_selection", "export",
]


class FieldSpec(BaseModel):
    name: str
    dtype: str
    unit: str | None = None
    role: Literal["base", "derived", "interaction"] | None = None
    requires_review: bool = False


class ClassDistribution(BaseModel):
    """priors per class; сумма ≈ 1.0 ± 1e-6"""
    priors: dict[str, float]


class FeatureRef(BaseModel):
    name: str
    role: Literal["base", "derived", "interaction", "temporal", "statistical"]


class ContextMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # identity
    conversation_id: UUID
    kb_version: str
    current_phase: Phase = "task_discovery"

    # task discovery
    user_request: str | None = None
    task_type: Literal["classification", "regression", "clustering",
                       "anomaly_detection", "ranking"] | None = None
    target_variable: str | None = None
    classes: list[str] | None = None
    domain: str | None = None
    data_source: str | None = None
    required_latency: str | None = None
    deployment_context: str | None = None

    # data profiling
    data_type: Literal["tabular", "time_series", "image", "tensor",
                       "graph", "event_log", "mixed"] | None = None
    data_volume: int | None = None
    update_frequency: str | None = None
    fields: list[FieldSpec] = Field(default_factory=list)
    missing_data_strategy: Literal[
        "none", "drop", "fill_zero", "fill_mean", "fill_median",
        "forward_fill",
    ] | None = None
    class_distribution: ClassDistribution | None = None
    temporal_importance: bool | None = None

    # domain context
    critical_factors: list[str] = Field(default_factory=list)
    interpretability_requirement: Literal["high", "medium", "low"] | None = None
    domain_constraints: list[str] = Field(default_factory=list)

    # rag
    rag_queries: list[str] = Field(default_factory=list)
    evidence_pack: dict | None = None

    # features
    base_features: list[FeatureRef] = Field(default_factory=list)
    derived_features: list[FeatureRef] = Field(default_factory=list)
    interaction_features: list[FeatureRef] = Field(default_factory=list)
    final_features: list[FeatureRef] = Field(default_factory=list)

    # data generation
    n_samples: int | None = None
    noise_level: float = 0.01
    anomaly_rate: float = 0.02
    random_state: int = 42
    generation_spec: dict | None = None
    generated_dataset: dict | None = None

    # model selection
    recommended_model: str | None = None
    selected_model: str | None = None
    model_ranking: list[dict] = Field(default_factory=list)
    training_config: dict | None = None

    # export
    artifacts: list[dict] = Field(default_factory=list)
    export_manifest: dict | None = None

    # control
    errors: list[dict] = Field(default_factory=list)
    validation_reports: list[dict] = Field(default_factory=list)
    user_feedback: list[dict] = Field(default_factory=list)
    iteration: int = 0
    updated_at: datetime
```

## Инварианты

См. [../04-domain/invariants.md#contextmemory](../04-domain/invariants.md).

## Что обновляет каждый агент

См. таблицу в [../01-business/glossary.md](../01-business/glossary.md) и реестр в [AGENTS.md](../../AGENTS.md).

## Сериализация

- В БД: JSONB по `conversation_id` + `phase`. Append-only снапшоты с `updated_at`.
- Между узлами LangGraph: in-process Pydantic объект.

## Связанные документы

- [../04-domain/entities.md#contextmemory](../04-domain/entities.md)
- [../04-domain/invariants.md](../04-domain/invariants.md)
- [structured-outputs.md](structured-outputs.md)
