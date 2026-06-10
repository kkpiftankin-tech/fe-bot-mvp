# Состояние машины

## Фазы

```text
initialization
  → task_discovery
    → data_profiling
      → domain_context
        → feature_synthesis
          → data_generation
            → model_selection
              → export
                → done
```

## Completion criteria по фазе

| Фаза | Completion criteria (всё true) |
| --- | --- |
| `initialization` | `conversation_id`, `kb_version`, `current_phase=task_discovery` |
| `task_discovery` | `task_type`, `target_variable` или `classes`, `domain`, `data_source` |
| `data_profiling` | `data_type`, `fields[] ≠ []`, `missing_data_strategy`; для classification — `class_distribution` |
| `domain_context` | `interpretability_requirement`, `critical_factors[] ≠ []` |
| `feature_synthesis` | `final_features[] ≠ []` + `user_confirmed=true` |
| `data_generation` | `generated_dataset.validation_passed=true` |
| `model_selection` | `selected_model`, `training_config` |
| `export` | `archive.zip` создан + manifest валиден |

Переход разрешён, только если completion-criteria текущей фазы выполнены. Иначе — clarification к пользователю, repair-loop, или откат.

## Условные edges

```text
NLUAgent → (intent=restart) → SessionAgent.restart → END_OF_OLD_SESSION
NLUAgent → (intent=clarify_feature, phase=feature_synthesis) → FeatureSynthesisAgent (mini-loop)
FeatureCriticAgent → (decision=failed) → FeatureSynthesisAgent (repair)
DataGenerationWorker → (validation_passed=false) → DataGenerationSpecAgent (repair)
HumanReview (feature) → (decision=rollback) → DataProfilingAgent (откат)
HumanReview (model) → (override) → ModelSelectionAgent (mini-loop)
```

## Инварианты

- Переход вперёд только при выполнении completion-criteria.
- Откат назад инвалидирует downstream-слоты (INV-CM-003).
- В каждой фазе максимум `max_retries=3` repair-loop-ов на ту же подзадачу.

## Связанные документы

- [graph-overview.md](graph-overview.md)
- [edges.md](edges.md)
- [repair-loops.md](repair-loops.md)
- [human-in-the-loop.md](human-in-the-loop.md)
- [../04-domain/invariants.md](../04-domain/invariants.md)
