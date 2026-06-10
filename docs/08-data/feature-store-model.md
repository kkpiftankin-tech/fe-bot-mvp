# Модель feature-store

## Назначение

Описать структуру feature-store, питающего домены analytics RAG-карточек и дашборд [ANALYTICS-08](../02-system/features/ANALYTICS-08-domain-feature-store.md).

## Кратко

Feature-store — это набор табличных аналитических представлений, агрегированных по окну T (час / день). Они вычисляются батч-worker-ом (`Batch Aggregation Worker`) из внешних источников и хранятся в PostgreSQL.

## Эталонные таблицы (бизнес-доменный пример)

### `sensor_analytics_T`

| Поле | Тип | Смысл |
| --- | --- | --- |
| `sensor_id` | str | id датчика |
| `window_start` | timestamp | начало окна T |
| `window_end` | timestamp | конец окна T |
| `uptime_ratio_T` | float [0..1] | доля времени online |
| `detection_probability_T` | float [0..1] | оцен. вероятность обнаружения |
| `false_alarm_rate_T` | float | ложные тревоги / окно |
| `avg_position_error` | float | средняя ошибка позиционирования |
| `track_drop_rate` | float [0..1] | доля потерянных треков |
| `revisit_time_mean` | float | среднее время обновления |
| `jammed_time_ratio` | float [0..1] | доля времени под помехами |

### `object_analytics_T`

| Поле | Тип | Смысл |
| --- | --- | --- |
| `object_id` | str | id объекта |
| `window_start`, `window_end` | timestamp | окно |
| `operational_availability_T` | float [0..1] | готовность |
| `route_deviation_index` | float | отклонение от плана маршрута |
| `signature_exposure_index` | float | заметность по сенсорам |
| `distance_to_threats_p05` | float | 5-й перцентиль расстояний до угроз |

### `environment_analytics_T`

| Поле | Тип | Смысл |
| --- | --- | --- |
| `region_id` | str | id региона |
| `radar_performance_factor` | float | усреднённая работоспособность РЛС |
| `electro_optical_effectiveness` | float | то же для EO/IR |
| `communication_reliability` | float | надёжность связи |
| `gnss_availability` | float | доступность GNSS |
| `sea_state` | int / float | состояние моря |
| `visibility` | float | видимость |

Дополнительно: `weapon_esm_analytics_T`, `comms_esm_analytics_T`, `global_situation_analytics_T` (см. бизнес-документ).

## Использование

- Эти показатели — кандидаты для `feature_pattern_card`-карточек.
- Аналитические `analytics_card`-карточки в RAG ссылаются на них как на источники.
- Dashboard [ANALYTICS-08](../02-system/features/ANALYTICS-08-domain-feature-store.md) рендерит их per-entity.

## Связанные документы

- [../02-system/features/ANALYTICS-08-domain-feature-store.md](../02-system/features/ANALYTICS-08-domain-feature-store.md)
- [../06-rag/document-types.md](../06-rag/document-types.md)
