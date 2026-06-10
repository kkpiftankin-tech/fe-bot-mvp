# ModelSelectionAgent

## Purpose

Эмитить ранжированный `ModelRecommendation` + `TrainingConfig`, опираясь на `task_type`, `data_type`, `data_volume`, `interpretability_requirement`, `required_latency`, `deployment_context`.

## Phase

`PHASE_6_MODEL_SELECTION`

## Input

- `ContextMemory` (полный).
- `EvidencePack` с `model_recommendation`-карточками.

## Output

`ModelRecommendation` + вложенный `TrainingConfig` — см. `schemas/model_recommendation.py`.

## Tools

- `metric_library.lookup(task_type)` — подбор `f1_macro`, `balanced_accuracy`, `roc_auc_ovr` и т. п.
- `cv_strategy.recommend(task_type, class_distribution)`.

## RAG Policy

```yaml
phase: model_selection
doc_type:
  - model_recommendation_card
task_type: current.task_type
data_type: current.data_type
top_k: 5
```

## Hard Rules

- top-1 модель обязана быть совместима с `task_type` × `data_type` (например, не предлагать `CNN` для `tabular`).
- Если `interpretability_requirement=high`, top-1 обязан поддерживать feature-importance или explainability.
- `training_config.metrics` обязан включать метрику, согласованную с `task_type` (для multiclass classification — `f1_macro` и `balanced_accuracy`).
- `random_state` обязан быть зафиксирован.

## Failure Modes

- 0 совместимых карточек → fallback на дефолтный список (см. `prompts/model_selection_agent.md`); `confidence_level=low`.
- Конфликт пользователь-override / hard-rules → агент эмитит структурированную ошибку, не уважает невалидный override.
