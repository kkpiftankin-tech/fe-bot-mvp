# FeatureCriticAgent

## Purpose

Детерминированно валидировать `FeatureCandidateSet` и эмитить `ValidationReport` с per-feature статусами и причинами.

## Phase

`PHASE_4_FEATURE_SYNTHESIS`

## Input

- `FeatureCandidateSet` (от FeatureSynthesisAgent).
- `ContextMemory.fields`, `temporal_importance`, `task_type`.
- `EvidencePack` с `validation_rule_card`-ами.

## Output

`ValidationReport` — см. `schemas/validation_report.py`.

## Tools

- `feature_validator.run(candidates, context)` — см. `validators/feature_validator.py`.

## RAG Policy

```yaml
phase: feature_synthesis
doc_type:
  - validation_rule_card
task_type: current.task_type
domain: current.domain
top_k: 5
```

## Hard Rules

- Сам не вызывает LLM — это детерминированный проверщик.
- Все правила инкапсулированы в `validators/feature_validator.py`; промпт-черновик только формирует «человекочитаемое» reasoning для UI.
- Отвергнутый признак не может быть «амнистирован» этим агентом; только пользователь в Human Review может override-нуть с обоснованием.

## Failure Modes

- Невалидная формула → `decision=rejected`, `reason=formula_parse_failed`.
- Циклические зависимости input_features → `decision=rejected`, `reason=cyclic_dependency`.
- Отсутствие evidence → `decision=rejected`, `reason=no_evidence`.
