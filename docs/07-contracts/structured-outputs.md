# Структурированные выводы агентов

Каждый агент возвращает Pydantic-объект конкретного типа. Сборные имена контрактов — в `schemas/agent_outputs.py`; узкие — в отдельных файлах.

| Агент | Output-схема | Файл |
| --- | --- | --- |
| `SessionAgent` | `SessionStartResponse` | `schemas/agent_outputs.py` |
| `NLUAgent` | `ParsedUserInput` | `schemas/agent_outputs.py` |
| `RAGRetrievalAgent` | `EvidencePack` | `schemas/agent_outputs.py` |
| `DialogueOrchestratorAgent` | `OrchestrationDecision` | `schemas/agent_outputs.py` |
| `ContextMemoryAgent` | `ContextMemoryUpdateResult` | `schemas/agent_outputs.py` |
| `TaskDiscoveryAgent` | `TaskDiscoveryResult` | `schemas/agent_outputs.py` |
| `DataProfilingAgent` | `DataProfile` | `schemas/agent_outputs.py` |
| `DomainContextAgent` | `DomainContext` | `schemas/agent_outputs.py` |
| `FeatureSynthesisAgent` | `FeatureCandidateSet` | `schemas/agent_outputs.py` |
| `FeatureCriticAgent` | `ValidationReport` | `schemas/validation_report.py` |
| `MulticollinearityAgent` | `MulticollinearityReport` | `schemas/validation_report.py` |
| `DataGenerationSpecAgent` | `GenerationSpec` | `schemas/generation_spec.py` |
| `ModelSelectionAgent` | `ModelRecommendation` | `schemas/model_recommendation.py` |
| `ExportAgent` | `ExportManifest` | `schemas/export_manifest.py` |
| `FeedbackAgent` | `FeedbackDecision` | `schemas/agent_outputs.py` |
| `AuditAgent` | `AuditNode` | `schemas/audit.py` |

## Общие поля

Где применимо, агенты возвращают:

```python
class CommonAgentOutput(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_doc_ids: list[str] = Field(default_factory=list)
    need_more_context: bool = False
    clarification: str | None = None   # если need_more_context=True
```

Конкретные output-схемы наследуют от этого или включают поля композицией.

## ParsedUserInput (NLU)

```python
class ParsedUserInput(CommonAgentOutput):
    intent: Literal[
        "describe_task", "describe_data", "request_features", "clarify_feature",
        "confirm_features", "generate_data", "recommend_model", "export_config",
        "restart", "unknown",
    ]
    entities: dict[str, EntityValue]
    missing_slots: list[str] = Field(default_factory=list)


class EntityValue(BaseModel):
    value: str
    confidence: float
```

## TaskDiscoveryResult

```python
class TaskDiscoveryResult(CommonAgentOutput):
    task_type: TaskType | None
    target_variable: str | None
    classes: list[str] | None
    domain: str | None
    data_source: str | None
    required_latency: str | None
    deployment_context: str | None
    open_questions: list[str] = Field(default_factory=list)
```

## DataProfile

```python
class DataProfile(CommonAgentOutput):
    data_type: DataType
    data_volume: int | None
    fields: list[FieldSpec]
    missing_data_strategy: str
    class_distribution: ClassDistribution | None
    temporal_importance: bool
    open_questions: list[str] = Field(default_factory=list)
```

## DomainContext

```python
class DomainContext(CommonAgentOutput):
    critical_factors: list[str]
    interpretability_requirement: Literal["high", "medium", "low"]
    domain_constraints: list[str] = Field(default_factory=list)
```

## FeatureCandidateSet / FeatureSpec / GenerationSpec / ModelRecommendation / ValidationReport / ExportManifest

См. отдельные документы:

- [feature-spec.md](feature-spec.md)
- [generation-spec.md](generation-spec.md)
- [validation-report.md](validation-report.md)

## Repair Loop

При сбое `model_validate` runtime собирает `RepairRequest`:

```python
class RepairRequest(BaseModel):
    original_input: dict
    previous_output: dict
    validation_report: ValidationReport
    attempt: int                # 1-indexed
    max_retries: int
```

И переотправляет агенту с явным запретом менять что-либо кроме listed issues.

## Связанные документы

- [context-memory.md](context-memory.md)
- [feature-spec.md](feature-spec.md)
- [generation-spec.md](generation-spec.md)
- [validation-report.md](validation-report.md)
- [../00-methodology/prompt-engineering-rules.md](../00-methodology/prompt-engineering-rules.md)
