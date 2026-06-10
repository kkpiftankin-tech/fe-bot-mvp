# ValidationReport / MulticollinearityReport

Унифицированный формат отчёта детерминированного валидатора.

## Pydantic-схема

```python
from typing import Literal
from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "error"]
Decision = Literal["passed", "failed", "warning", "needs_review"]


class ValidationFinding(BaseModel):
    target_id: str            # feature.name, doc_id, generation_spec.field.name и т. п.
    severity: Severity
    code: str                 # стабильный машиночитаемый код, e.g. "FEAT_001_UNKNOWN_INPUT"
    message: str              # человекочитаемое
    metadata: dict = Field(default_factory=dict)


class ValidationReport(BaseModel):
    validator_name: str
    target_kind: Literal[
        "feature", "feature_set", "generation_spec", "generated_dataset",
        "context_memory", "rag_card", "export_manifest", "training_config",
    ]
    decision: Decision
    findings: list[ValidationFinding] = Field(default_factory=list)
    summary: str | None = None


class CorrelatedPair(BaseModel):
    a: str
    b: str
    rho: float                # [-1.0, 1.0]
    severity: Severity


class MulticollinearityReport(BaseModel):
    pairs: list[CorrelatedPair] = Field(default_factory=list)
    vif: dict[str, float] = Field(default_factory=dict)   # feature_name → VIF
    recommendations: list[str] = Field(default_factory=list)
    confidence_level: Literal["high", "medium", "low"] = "medium"
```

## Коды (выборка)

| Код | Где эмитится |
| --- | --- |
| `FEAT_001_UNKNOWN_INPUT` | feature_validator |
| `FEAT_002_FORMULA_PARSE_FAILED` | feature_validator |
| `FEAT_003_NO_EVIDENCE` | feature_validator |
| `FEAT_004_TEMPORAL_DISALLOWED` | feature_validator |
| `FEAT_005_HIGH_CORR_PAIR` | multicollinearity |
| `FEAT_006_VIF_HIGH` | multicollinearity |
| `GEN_001_PRIORS_SUM_MISMATCH` | generation_spec_validator |
| `GEN_002_DERIVED_INPUT_MISSING` | generation_spec_validator |
| `GEN_003_TEMPORAL_DISALLOWED` | generation_spec_validator |
| `DATA_001_NAN_PRESENT` | generated_data_validator |
| `DATA_002_INF_PRESENT` | generated_data_validator |
| `DATA_003_SHAPE_MISMATCH` | generated_data_validator |
| `DATA_004_CLASS_BALANCE_OFF` | generated_data_validator |
| `RAG_001_MISSING_FIELD` | rag_metadata_validator |
| `RAG_002_UNKNOWN_DOC_TYPE` | rag_metadata_validator |
| `RAG_003_UNKNOWN_DOMAIN` | rag_metadata_validator |
| `EXPORT_001_MISSING_ARTIFACT` | export_manifest_validator |

## Связь с repair-loop

Если `decision = failed`, runtime собирает `RepairRequest` (см. [structured-outputs.md](structured-outputs.md)) с этим отчётом и переотправляет агенту.

## Связанные документы

- [structured-outputs.md](structured-outputs.md)
- [feature-spec.md](feature-spec.md)
- [generation-spec.md](generation-spec.md)
- [../../validators/](../../validators/)
