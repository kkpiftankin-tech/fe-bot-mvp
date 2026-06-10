# ADR-004. LLM эмитит GenerationSpec, а не строки датасета

## Status

Accepted

## Context

При генерации синтетического обучающего датасета (100k × 19) есть два очевидных подхода:

1. **Прямой:** LLM генерирует строки CSV токенами.
2. **Косвенный:** LLM эмитит `GenerationSpec` (типы распределений, class priors, формулы производных, модели шума и аномалий), а Python-worker строит датасет.

Прямой подход проваливается по нескольким причинам:

- Производительность: маленький LLM (1B–3B) и 100k строк по 19 значений = ≈ 1.9M токенов. Это часы CPU-инференса.
- Валидация: невозможно гарантировать `no NaN / no Inf / class balance` на токенах.
- Воспроизводимость: даже с фиксированным seed sampling в LLM не байт-стабилен.
- Стоимость: невыгодно даже в облачных моделях.

## Decision

LLM эмитит **только** `GenerationSpec` (Pydantic-схема). `DataGenerationWorker` (Python с `numpy`/`pandas`/`scipy`) производит датасет из спецификации.

Спецификация описывает:

- `n_samples`, `random_state`.
- target: `name`, `type`, `classes[]` с `prior` и optional `class_conditional_distributions`.
- `feature_specs[]`: для base — `distribution`; для derived — `formula`; для interaction — `formula`.
- `noise`, `anomalies`, `validation` (ожидания проверок).

## Consequences

- Положительные:
  - Воспроизводимость по `random_state` (NFR-Repro-001).
  - Дешёвая генерация: один LLM-вызов на сессию, остальное — `numpy` за секунды.
  - Валидируемость: `validators/generation_spec_validator.py` + `validators/generated_data_validator.py`.
  - Спецификация версионируема и читаема пользователем.
- Отрицательные:
  - Усложнение: нужен парсер формул и безопасный evaluator. Реализация в `src/fe_bot/data_generation/`.
  - Расширение на новые task-types (image/sequence) требует расширения `GenerationSpec` и worker-а.
- Нейтральные:
  - При желании сменить движок генерации (например, на `sdv` или `gretel`) интерфейс остаётся стабильным: вход — `GenerationSpec`.

## Related

- [../../02-system/features/RUNTIME-09-generation-spec.md](../../02-system/features/RUNTIME-09-generation-spec.md)
- [../../02-system/features/RUNTIME-10-data-generation.md](../../02-system/features/RUNTIME-10-data-generation.md)
- [../../07-contracts/generation-spec.md](../../07-contracts/generation-spec.md)
- [../../01-business/constraints.md](../../01-business/constraints.md)
