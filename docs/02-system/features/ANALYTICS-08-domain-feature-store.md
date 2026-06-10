# ANALYTICS-08. Аналитика доменного feature-store

## Назначение

Доменный дашборд поверх агрегатов feature-store (`sensor_analytics_T`, `weapon_esm_analytics_T`, `comms_esm_analytics_T`, `object_analytics_T`, `environment_analytics_T`, `global_situation_analytics_T`), пришедших из внешних источников.

## Бизнес-ценность

Многие реальные задачи переиспользуют те же доменные агрегаты, что движут предложениями признаков в Runtime. Делая их first-class видами, мы укорачиваем путь от вопроса «как сегодня выглядит датчик X?» до одного экрана.

## Пользовательский сценарий

Оператор открывает дашборд, выбирает датчик и видит `uptime_ratio_T`, `detection_probability_T`, `false_alarm_rate_T`, `avg_position_error`, `track_drop_rate`, `revisit_time_mean`, `jammed_time_ratio` за выбранное окно. Для объекта: `operational_availability_T`, `route_deviation_index`, `signature_exposure_index`, `distance_to_threats_p05`.

## Связанные требования

- BR-FR-Analytics-001..004 (per-entity панели, выбор окна, drill-down до источника).
- Определения признаков идут из analytics RAG-карточек в [`rag/cards/analytics_cards/`](../../../rag/cards/analytics_cards/).

## Связанные сервисы

- Domain Analytics Service, Feature Store, Data Source Connectors, Batch Aggregation Worker, RAG Analytics Cards, Frontend Analytics Dashboard.

## Связанные контракты

- `FeatureStoreReading` (`schemas/feature_store.py`): `entity_type`, `entity_id`, `feature_name`, `window`, `value`, `computed_at`.

## Критерии приёмки

- Панель ОБЯЗАНА отказываться рендериться, когда базовый агрегат отсутствует — она НЕ ОБЯЗАНА фабриковать значение.
- Drill-down от значения признака ОБЯЗАН указывать на исходную analytics-карточку.
- Тест: `tests/component/test_domain_feature_store_dashboard.py`.

## Вне scope

- Real-time streaming dashboards (MVP — batch).
