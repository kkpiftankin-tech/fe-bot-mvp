# Human-in-the-loop

## Когда HITL обязателен

| Точка | Что подтверждает пользователь | Что блокируется без подтверждения |
| --- | --- | --- |
| `task_discovery` | `task_type`, `classes`, `domain` (если NLU вернул confidence<1) | Переход в data_profiling |
| `data_profiling` | Список полей (нормализованный) и `temporal_importance` | Переход в domain_context |
| `domain_context` | `critical_factors`, `interpretability_requirement` | Переход в feature_synthesis |
| `feature_review` | `final_features` | Переход в data_generation |
| `model_review` | `selected_model` (override или accept) | Переход в export |

## Реализация в LangGraph

В LangGraph каждое HITL — это `interrupt`-узел. Runtime:

1. Эмитит «pending review» событие.
2. Сохраняет snapshot ContextMemory.
3. Возвращает управление API Backend, тот вызывает фронт.
4. После действия пользователя POST `/runtime/resume` с `FeedbackDecision`.
5. Граф resumes из точки interrupt.

## Откаты

- В feature_review «rollback to data_profiling» инвалидирует: `base_features`, `derived_features`, `interaction_features`, `final_features`, `generation_spec`, `generated_dataset`, `recommended_model`, `selected_model`, `training_config`, `artifacts`, `export_manifest`.
- Каждое HITL-действие эмитит audit event с `decided_by`, `decided_at`, `reason`.

## Аудит

| Событие | Когда |
| --- | --- |
| `feature_review_started` | до `interrupt` |
| `feature_review_decided` | после `/runtime/resume` |
| `model_review_started` | до `interrupt` |
| `model_review_decided` | после `/runtime/resume` |

## Связанные документы

- [state-machine.md](state-machine.md)
- [edges.md](edges.md)
- [../02-system/features/RUNTIME-08-feature-review.md](../02-system/features/RUNTIME-08-feature-review.md)
- [../02-system/features/RUNTIME-11-model-selection.md](../02-system/features/RUNTIME-11-model-selection.md)
