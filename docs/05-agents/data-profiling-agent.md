# DataProfilingAgent

## Purpose

Собрать `DataProfile`: `data_volume`, `data_type`, `update_frequency`, `fields[]`, `missing_data_strategy`, `class_distribution`, `temporal_importance`.

## Phase

`PHASE_2_DATA_PROFILING`

## Input

- `ContextMemory` (`task_type`, `domain`, `data_source`).
- `EvidencePack` с `schema_card`-ами и `question_template`-ами.

## Output

`DataProfile` — см. `schemas/agent_outputs.py`.

## Tools

- `schema_card.lookup(field_name)` — нормализация полей (`РЛС/ЭПР` → `radar/rcs`).
- `class_distribution.validate(priors)` — проверка суммы.

## RAG Policy

```yaml
phase: data_profiling
doc_type:
  - schema_card
  - question_template_card
domain: current.domain
data_source: current.data_source
top_k: 5
```

## Hard Rules

- Сумма `class_distribution.priors` обязана быть 1.0 ± 1e-6.
- При `temporal_importance=true` в `fields` обязаны быть `timestamp` и `entity_id` — иначе блок-вопрос пользователю.
- Неизвестное поле помечать `requires_review=true`, не отбрасывать.

## Failure Modes

- Поле не находится в `schema_card`-ах → пометить `custom_field`, поднять `needs_review`.
- Несогласованные dtypes (например, `range` объявлен как `str`) → запросить подтверждение пользователя.
