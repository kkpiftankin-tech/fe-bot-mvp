# DataGenerationSpecAgent

## Purpose

Эмитировать `GenerationSpec` — Python-консумируемый JSON, описывающий распределения, target-логику, шум и аномалии. **LLM эмитит spec, никогда не строки.**

## Phase

`PHASE_5_DATA_GENERATION`

## Input

- `ContextMemory.final_features`, `class_distribution`, `n_samples`, `noise_level`, `anomaly_rate`, `temporal_importance`.
- `EvidencePack` с `feature_pattern`, `analytics_card`, `validation_rule`-карточками.

## Output

`GenerationSpec` — см. `schemas/generation_spec.py`.

## Tools

- `class_distribution.normalize(priors)`.
- `distribution_library.suggest(feature, domain)` — рекомендация распределения по карточкам.

## RAG Policy

```yaml
phase: data_generation
doc_type:
  - feature_pattern_card
  - analytics_card
  - validation_rule_card
domain: current.domain
data_source: current.data_source
top_k: 8
```

## Hard Rules

- Не эмитить строки данных, только spec.
- `target.classes[*].prior` обязаны суммироваться к 1.0 ± 1e-6.
- Производные spec обязаны ссылаться только на ранее определённые признаки.
- Запрещены временные распределения, если `temporal_importance=false`.

## Failure Modes

- `generation_spec_validator` отверг → repair-loop (max 3) с приложенным отчётом.
- Невозможно определить параметры распределения для редкого признака → возвращать `distribution.type=default_by_dtype` + `confidence=low`.
