# Prompt evaluation

## Назначение

Убедиться, что маленькая LLM на текущем промпте возвращает JSON, валидируемый Pydantic-схемой агента, для набора curated-кейсов.

## Кейсы

Файлы под [`tests/prompt_eval/`](../../tests/prompt_eval/). По одному файлу на агента:

- `nlu_agent_cases.yaml`
- `task_discovery_agent_cases.yaml`
- `data_profiling_agent_cases.yaml`
- `domain_context_agent_cases.yaml`
- `feature_synthesis_agent_cases.yaml`
- `feature_critic_agent_cases.yaml`
- `generation_spec_agent_cases.yaml`
- `model_selection_agent_cases.yaml`
- `setup_card_generation_cases.yaml`

Каждый кейс:

```yaml
- name: classifier_naval_radar
  context_memory: { task_type: classification, domain: naval, data_source: radar, ... }
  evidence_pack: { items: [...] }
  expectations:
    schema_valid: true
    intent: describe_task     # для NLU
    must_include_entity: [task_type, domain, data_source]
    confidence_min: 0.7
```

## Метрики

- `schema_validity_rate ≥ 0.95`.
- `intent_accuracy ≥ 0.85` (NLU).
- `entity_accuracy ≥ 0.80` (NLU).
- `repair_loop_rate ≤ 0.10`.

## Версионирование

Каждый кейс несёт `prompt_template_version`. При bump промпта обновляются (или добавляются) кейсы.

## Запуск

```bash
make test-prompt
```
