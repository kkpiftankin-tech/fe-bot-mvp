# Модель сгенерированных данных

## Назначение

Описать форму, типы и инварианты данных, производимых `DataGenerationWorker`-ом из `GenerationSpec`.

## Файлы

| Файл | Формат | Содержимое |
| --- | --- | --- |
| `X_train.csv` | CSV (UTF-8, comma, заголовок) | Признаки, по одной строке на семпл |
| `y_train.npy` | NumPy NPY | Метки целевой переменной |
| `metadata.json` | JSON | Provenance, shapes, фактические priors, hashes |
| `validation_report.json` | JSON | Результат `generated_data_validator` |

## Инварианты

- `X.shape == (n_samples, len(final_features))`.
- `y.shape == (n_samples,)`.
- Для классификации `y ∈ {0, ..., n_classes - 1}`.
- Нет NaN/Inf при `missing_data_strategy = none` (INV-Gen-005).
- Фактические priors классов в `[prior - 0.01, prior + 0.01]` (INV-Gen-006).
- Перезапуск с тем же `(spec, random_state)` даёт байт-идентичный X+y (INV-Gen-004).

## Структура `metadata.json`

```json
{
  "dataset_id": "ds_2026_05_18_001",
  "conversation_id": "conv_001",
  "kb_version": "kb_2026_05_18_v1",
  "spec_version": "1.0",
  "generation_mode": "tabular_classification",
  "n_samples": 100000,
  "n_features": 19,
  "n_classes": 4,
  "class_names": ["civilian_ship", "military_ship", "submarine", "aircraft"],
  "class_distribution_requested": {"civilian_ship": 0.4, "military_ship": 0.3, "submarine": 0.2, "aircraft": 0.1},
  "class_distribution_actual": {"civilian_ship": 0.3998, "military_ship": 0.3002, "submarine": 0.2, "aircraft": 0.1},
  "noise_level": 0.01,
  "anomaly_rate": 0.02,
  "actual_anomaly_rate": 0.0203,
  "random_state": 42,
  "files": {
    "X_train": {"path": "X_train.csv", "sha256": "..."},
    "y_train": {"path": "y_train.npy", "sha256": "..."}
  },
  "created_at": "2026-05-18T00:00:00Z",
  "validation": {
    "no_nan": true, "no_inf": true,
    "valid_y_values": true,
    "class_distribution_balanced": true,
    "shape_correct": true
  }
}
```

## Связанные документы

- [../07-contracts/generation-spec.md](../07-contracts/generation-spec.md)
- [artifact-model.md](artifact-model.md)
- [../02-system/features/RUNTIME-10-data-generation.md](../02-system/features/RUNTIME-10-data-generation.md)
- [../../validators/generated_data_validator.py](../../validators/generated_data_validator.py)
