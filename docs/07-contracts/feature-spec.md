# FeatureSpec / FeatureCandidate

## Pydantic-схема

```python
from typing import Literal
from pydantic import BaseModel, Field, model_validator

FeatureRole = Literal["base", "derived", "interaction", "temporal", "statistical"]
RiskLevel = Literal["low", "medium", "high"]
FeatureStatus = Literal["candidate", "approved", "rejected", "needs_review"]


class FeatureCandidate(BaseModel):
    name: str
    role: FeatureRole
    dtype: str                         # "float32", "int", "category" ...
    description: str = Field(max_length=200)
    formula: str | None = None
    input_features: list[str] = Field(default_factory=list)
    source_fields: list[str] = Field(default_factory=list)
    evidence_doc_ids: list[str] = Field(default_factory=list)
    feature_family: str | None = None
    unit: str | None = None
    leakage_risk: RiskLevel = "low"
    risk_level: RiskLevel = "low"

    @model_validator(mode="after")
    def _check(self):
        if self.role == "base":
            if not self.source_fields:
                raise ValueError("base feature must have source_fields")
            if self.formula:
                raise ValueError("base feature must not have a formula")
        if self.role in ("derived", "interaction"):
            if not self.formula:
                raise ValueError(f"{self.role} feature must have a formula")
            if not self.input_features:
                raise ValueError(f"{self.role} feature must reference input_features")
        return self


class FeatureSpec(FeatureCandidate):
    status: FeatureStatus
    validation_rules: list[str] = Field(default_factory=list)
    rejected_reason: str | None = None

    @model_validator(mode="after")
    def _approved_must_have_evidence(self):
        if self.status == "approved" and not self.evidence_doc_ids:
            raise ValueError("approved feature requires evidence_doc_ids")
        if self.status == "rejected" and not self.rejected_reason:
            raise ValueError("rejected feature requires rejected_reason")
        return self


class FeatureCandidateSet(BaseModel):
    features: list[FeatureCandidate]
    notes: str | None = None
```

## Контракт `evidence_doc_ids`

- Любой `approved`-признак обязан иметь непустой `evidence_doc_ids` (INV-Feat-001).
- Каждый `doc_id` обязан существовать в активной KB-версии (форсится в Critic-агенте через ссылку на EvidencePack).

## Контракт `input_features`

- Для `derived` — все имена обязаны существовать в `ContextMemory.fields` или среди ранее принятых признаков.
- Для `interaction` — все имена обязаны быть в `final_features` к моменту попадания признака в `final_features` (топологический порядок).

## Лимиты

- `MAX_FEATURES = 200` всего в `final_features`.
- `MAX_INTERACTIONS = 50` среди interaction-признаков.

## Связанные документы

- [structured-outputs.md](structured-outputs.md)
- [validation-report.md](validation-report.md)
- [../04-domain/invariants.md](../04-domain/invariants.md)
- [../../validators/feature_validator.py](../../validators/feature_validator.py)
