# TaskDiscoveryAgent

## Purpose

Установить `task_type`, `target_variable`, `classes` (для классификации), `domain`, `data_source`, `required_latency`, `deployment_context`. Задаёт уточняющие вопросы при недостаче слотов.

## Phase

`PHASE_1_TASK_DISCOVERY`

## Input

- `ParsedUserInput`.
- `ContextMemory` (текущие слоты).
- `EvidencePack` с `domain_profile`-карточками и `question_template`-карточками.

## Output

`TaskDiscoveryResult` — см. `schemas/agent_outputs.py`.

## Tools

- `glossary_lookup(term)` для нормализации классов.
- `question_template.select(missing_slot)`.

## RAG Policy

```yaml
phase: task_discovery
doc_type:
  - domain_profile
  - question_template_card
domain: current.domain
data_source: current.data_source
top_k: 3
```

## Hard Rules

- `task_type` ∈ `{classification, regression, clustering, anomaly_detection, ranking}`.
- Если `task_type=classification`, `classes` обязательны; пустой список — это `need_more_context`.
- Не выдумывать `domain` без подтверждающей `domain_profile`-карточки.

## Failure Modes

- Пользователь не отвечает на уточняющий вопрос → перепроще на чёрно-белый выбор (например, чек-боксы).
- Из 2 шагов не удалось установить task_type → передать `need_more_context=true` со списком конкретных недостающих слотов.
