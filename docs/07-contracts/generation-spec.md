# GenerationSpec

## Pydantic-схема

```python
from typing import Literal, Annotated
from pydantic import BaseModel, Field, model_validator


class TargetClass(BaseModel):
    id: int
    name: str
    prior: Annotated[float, Field(ge=0.0, le=1.0)]


class TargetSpec(BaseModel):
    name: str
    type: Literal["binary", "multiclass", "regression"]
    classes: list[TargetClass] | None = None   # обяз. для классов
    range: tuple[float, float] | None = None   # для regression


class DistributionSpec(BaseModel):
    type: Literal[
        "uniform", "normal", "lognormal", "exponential",
        "poisson", "beta", "binomial", "categorical", "default_by_dtype",
    ]
    params: dict[str, float | int | list] = Field(default_factory=dict)


class FeatureGenSpec(BaseModel):
    name: str
    role: Literal["base", "derived", "interaction"]
    dtype: str
    unit: str | None = None
    distribution: DistributionSpec | None = None        # base
    formula: str | None = None                          # derived/interaction
    input_features: list[str] = Field(default_factory=list)
    distribution_by_class: dict[str, DistributionSpec] | None = None  # conditional generation


class NoiseSpec(BaseModel):
    type: Literal["gaussian", "uniform", "none"] = "gaussian"
    std: float = 0.01


class AnomalySpec(BaseModel):
    rate: Annotated[float, Field(ge=0.0, le=0.2)] = 0.02
    type: Literal[
        "multiplicative_sensor_glitch", "additive_outlier", "label_flip", "none",
    ] = "multiplicative_sensor_glitch"
    factor_min: float | None = 2.0
    factor_max: float | None = 5.0


class ValidationExpectations(BaseModel):
    expected_X_shape: tuple[int, int] | None = None
    expected_y_shape: tuple[int] | None = None
    required_checks: list[str] = Field(default_factory=lambda: [
        "no_nan", "no_inf", "valid_y_values", "class_distribution_balanced",
    ])


class GenerationSpec(BaseModel):
    spec_version: str = "1.0"
    generation_mode: Literal[
        "tabular_classification", "tabular_regression",
        "sequence_forecasting", "radar_tensor_detection",
        "spectrogram_classification", "track_sequence_classification",
    ]
    n_samples: Annotated[int, Field(ge=100, le=1_000_000)]
    random_state: int = 42

    target: TargetSpec
    feature_specs: list[FeatureGenSpec]

    noise: NoiseSpec = Field(default_factory=NoiseSpec)
    anomalies: AnomalySpec = Field(default_factory=AnomalySpec)
    validation: ValidationExpectations = Field(default_factory=ValidationExpectations)

    @model_validator(mode="after")
    def _consistency(self):
        if self.target.type in ("binary", "multiclass"):
            if not self.target.classes:
                raise ValueError("classification target requires classes")
            priors = [c.prior for c in self.target.classes]
            if abs(sum(priors) - 1.0) > 1e-6:
                raise ValueError("class priors must sum to 1.0 ± 1e-6")

        names = {f.name for f in self.feature_specs}
        for f in self.feature_specs:
            if f.role in ("derived", "interaction"):
                if not f.formula:
                    raise ValueError(f"{f.name}: derived/interaction must have formula")
                for inp in f.input_features:
                    if inp not in names and inp not in {"timestamp", "entity_id"}:
                        raise ValueError(f"{f.name}: unknown input_feature {inp}")
            else:  # base
                if not f.distribution and not f.distribution_by_class:
                    raise ValueError(f"{f.name}: base feature requires distribution")

        return self
```

## Пример

См. § 8 в `Обучающий_материал` и § 21 в `Бизнес.md`. В кратком виде:

```json
{
  "spec_version": "1.0",
  "generation_mode": "tabular_classification",
  "n_samples": 100000,
  "random_state": 42,
  "target": {
    "name": "target_type",
    "type": "multiclass",
    "classes": [
      {"id": 0, "name": "civilian_ship", "prior": 0.4},
      {"id": 1, "name": "military_ship", "prior": 0.3},
      {"id": 2, "name": "submarine", "prior": 0.2},
      {"id": 3, "name": "aircraft", "prior": 0.1}
    ]
  },
  "feature_specs": [
    {"name": "range", "role": "base", "dtype": "float32",
     "distribution": {"type": "uniform", "params": {"min": 0, "max": 200}}},
    {"name": "rcs", "role": "base", "dtype": "float32",
     "distribution": {"type": "exponential", "params": {"scale": 10}}},
    {"name": "snr", "role": "base", "dtype": "float32",
     "distribution": {"type": "normal", "params": {"mean": 20, "std": 10}}},
    {"name": "rcs_normalized", "role": "derived", "dtype": "float32",
     "formula": "log1p(rcs)", "input_features": ["rcs"]},
    {"name": "range_x_snr", "role": "interaction", "dtype": "float32",
     "formula": "range * snr / 100.0", "input_features": ["range", "snr"]}
  ],
  "noise": {"type": "gaussian", "std": 0.01},
  "anomalies": {"rate": 0.02, "type": "multiplicative_sensor_glitch",
                 "factor_min": 2, "factor_max": 5},
  "validation": {
    "expected_X_shape": [100000, 19],
    "expected_y_shape": [100000],
    "required_checks": ["no_nan", "no_inf", "valid_y_values", "class_distribution_balanced"]
  }
}
```

## Связанные документы

- [structured-outputs.md](structured-outputs.md)
- [feature-spec.md](feature-spec.md)
- [../03-architecture/adr/ADR-004-llm-generates-spec-not-data.md](../03-architecture/adr/ADR-004-llm-generates-spec-not-data.md)
- [../../validators/generation_spec_validator.py](../../validators/generation_spec_validator.py)
