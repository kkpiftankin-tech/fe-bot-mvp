# FeatureSynthesisAgent

## Purpose

Сгенерировать `FeatureCandidateSet` — список base / derived / interaction-признаков с формулами, input-полями и `evidence_doc_ids`.

## Phase

`PHASE_4_FEATURE_SYNTHESIS`

## Input

- `ContextMemory.fields`, `critical_factors`, `interpretability_requirement`, `task_type`, `temporal_importance`.
- `EvidencePack` с `feature_pattern`, `analytics_card`, `schema_card`, `glossary`.

## Output

`FeatureCandidateSet` — см. `schemas/agent_outputs.py`.

## Tools

- `formula_parser.validate(formula, available_fields)` — безопасный evaluator.
- `feature_library.suggest(domain, task_type)` — поиск шаблонных признаков.

## RAG Policy

```yaml
phase: feature_synthesis
doc_type:
  - feature_pattern_card
  - analytics_card
  - schema_card
  - glossary_term
domain: current.domain
data_source: current.data_source
task_type: current.task_type
top_k: 10
```

## Hard Rules

- Не выдумывать поля: каждое `source_fields[i]` — из `ContextMemory.fields`.
- При `temporal_importance=false` запрещено эмитить признаки с `role=temporal`.
- Каждый признак обязан нести `evidence_doc_ids`; пустой evidence → признак отбрасывается до отправки в Critic.
- Лимиты: ≤ `MAX_FEATURES` всего, ≤ `MAX_INTERACTIONS` для interaction-признаков.

## Failure Modes

- Validation Critic отверг ≥ 30 % → запустить repair-loop с приложенным `ValidationReport`.
- После `max_retries` фаза фейлится, пользователь видит структурированный список причин и опцию вернуться в Data Profiling.
