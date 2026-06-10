# Value Objects

Объекты без identity. Равенство — по значению. Используются как поля сущностей.

## Phase

```python
Phase = Literal[
    "initialization",
    "task_discovery",
    "data_profiling",
    "domain_context",
    "feature_synthesis",
    "data_generation",
    "model_selection",
    "export",
]
```

## TaskType

```python
TaskType = Literal[
    "classification",
    "regression",
    "clustering",
    "anomaly_detection",
    "ranking",
]
```

## DataType

```python
DataType = Literal[
    "tabular",
    "time_series",
    "image",
    "tensor",
    "graph",
    "event_log",
    "mixed",
]
```

## InterpretabilityRequirement

```python
InterpretabilityRequirement = Literal["high", "medium", "low"]
```

## FeatureRole

```python
FeatureRole = Literal["base", "derived", "interaction", "temporal", "statistical"]
```

## RiskLevel

```python
RiskLevel = Literal["low", "medium", "high"]
```

## ConfidenceLevel

```python
ConfidenceLevel = Literal["high", "medium", "low"]
```

## CardType

```python
CardType = Literal[
    "ontology_card",
    "domain_profile",
    "schema_card",
    "task_card",
    "feature_pattern_card",
    "analytics_card",
    "validation_rule_card",
    "question_template_card",
    "example_card",
    "bad_example_card",
    "glossary_term",
]
```

## ChunkType

```python
ChunkType = Literal[
    "summary",
    "definition",
    "inputs",
    "outputs",
    "formula",
    "validation_rules",
    "examples",
    "agent_usage",
    "constraints",
]
```

## RAGMetadata

```python
class RAGMetadata(BaseModel):
    doc_id: str
    doc_type: CardType
    title: str
    phase: list[Phase]
    domain: list[str]
    data_source: list[str] | None = None
    task_type: list[TaskType] | None = None
    retrieval_tags: list[str]
    feature_family: str | None = None
    requires_temporal_sequence: bool = False
    confidence_level: ConfidenceLevel
    version: str  # SemVer
    owner: str
    last_updated_at: datetime
```

## TextOffsets

```python
class TextOffsets(BaseModel):
    start: int
    end: int
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None
```

## ClassDistribution

```python
class ClassDistribution(RootModel[dict[str, float]]):
    """priors на класс; сумма ≈ 1.0 ± 1e-6"""
```

## DistributionSpec

```python
DistributionType = Literal[
    "uniform", "normal", "lognormal", "exponential",
    "poisson", "beta", "binomial", "categorical", "default_by_dtype",
]

class DistributionSpec(BaseModel):
    type: DistributionType
    # Параметры зависят от type; см. validators/generation_spec_validator.py
    params: dict[str, float | int | list]
```

## NoiseSpec / AnomalySpec

```python
class NoiseSpec(BaseModel):
    type: Literal["gaussian", "uniform", "none"]
    std: float = 0.0


class AnomalySpec(BaseModel):
    rate: float
    type: Literal["multiplicative_sensor_glitch", "additive_outlier", "label_flip", "none"]
    factor_min: float | None = None
    factor_max: float | None = None
```

## TrainingConfig

```python
class TrainingConfig(BaseModel):
    model: str
    task_type: TaskType
    n_classes: int | None
    n_features: int
    hyperparameters: dict
    preprocessing: dict
    validation: dict   # strategy, n_splits, random_state, test_size
    metrics: list[str]
    early_stopping: dict | None = None
    random_state: int = 42
```

## ArtifactKind

```python
ArtifactKind = Literal[
    "source_document",
    "rag_chunk_manifest",
    "x_train_csv",
    "y_train_npy",
    "features_json",
    "generation_spec_json",
    "training_config_yaml",
    "pipeline_py",
    "data_generator_py",
    "metadata_json",
    "validation_report_json",
    "archive_zip",
    "retrieval_report",
    "setup_session_snapshot",
]
```

## AuditKind

```python
AuditKind = Literal[
    "source_uploaded",
    "section_parsed",
    "card_generated",
    "card_reviewed",
    "kb_published",
    "session_started",
    "phase_advanced",
    "agent_run",
    "feature_confirmed",
    "spec_generated",
    "dataset_generated",
    "model_selected",
    "artifact_exported",
    "artifact_downloaded",
    "validation_failed",
    "repair_triggered",
]
```

## Связанные документы

- [entities.md](entities.md)
- [domain-events.md](domain-events.md)
- [../07-contracts/](../07-contracts/)
