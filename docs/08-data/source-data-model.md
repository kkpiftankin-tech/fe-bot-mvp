# Модель исходных данных

## Назначение

Описать, что FE-Bot считает «исходными данными» на каждой стадии и как они представлены.

## Source-документы (Setup)

Артефакты в [incoming-docs/raw/](../../incoming-docs/raw/) и [Source Registry](../02-system/features/SETUP-03-source-registry.md). Типизированы через [`SourceDocument`](../04-domain/entities.md).

## Пользовательский профиль данных (Runtime)

FE-Bot **не** загружает реальные пользовательские данные. На Runtime пользователь описывает их через `DataProfile`:

- `data_type`: tabular / time_series / image / ...
- `fields`: имена + dtype + units
- `data_volume`: количество строк
- `missing_data_strategy`: как обрабатывать пропуски
- `class_distribution`: priors для классов
- `temporal_importance`: есть ли временная ось

Эти сведения далее служат входом для генерации синтетического датасета.

## Эталонный сценарий (naval radar)

| Поле | dtype | unit | role |
| --- | --- | --- | --- |
| `range` | float32 | km | base |
| `azimuth` | float32 | deg | base |
| `elevation` | float32 | deg | base |
| `rcs` | float32 | m² | base |
| `snr` | float32 | dB | base |
| `doppler` | float32 | m/s | base |

Классы: `civilian_ship (0.4), military_ship (0.3), submarine (0.2), aircraft (0.1)`. `temporal_importance = false`. `data_volume = 50000`.

## Связанные документы

- [generated-data-model.md](generated-data-model.md)
- [../02-system/features/RUNTIME-04-data-profiling.md](../02-system/features/RUNTIME-04-data-profiling.md)
- [../04-domain/entities.md](../04-domain/entities.md)
