# RUNTIME-04. Data Profiling

## Назначение

Построить типизированный профиль данных пользователя: `data_volume`, `data_type` ∈ {`tabular`, `time_series`, `image`, `tensor`, `graph`, `event_log`, `mixed`}, `update_frequency`, `fields[]` (name + dtype + unit + role), `missing_data_strategy`, `class_distribution`, `temporal_importance`.

## Бизнес-ценность

И синтез признаков, и генерация синтетических данных зависят от знания формы и семантики входа. Профилирование делает эти допущения явными, пока они не превратились в скрытые баги.

## Вход и выход

- **Вход.** Ответы пользователя с *описанием* данных — объём, поля, пропуски, распределение классов, роль времени (сами данные не загружаются); schema-карточки базы знаний для нормализации имён полей.
- **Выход.** `DataProfile`: слоты `data_type`, `data_volume`, `fields`, `missing_data_strategy`, `class_distribution`, `temporal_importance` в `ContextMemory`; неизвестные поля сохраняются как `custom_field` с `requires_review`.

## Пользовательский сценарий

Агент задаёт структурированные вопросы по очереди: *«Какой объём данных? Какие поля? Есть ли пропуски? Каково распределение классов? Важна ли временная ось?»* Для radar-примера агент нормализует `Range, Azimuth, RCS, SNR, Doppler` против schema-карточек и фиксирует:

```yaml
data_volume: 50000
data_type: tabular
fields: [range, azimuth, elevation, rcs, snr, doppler]
missing_data_strategy: none
class_distribution: {civilian_ship: 0.4, military_ship: 0.3, submarine: 0.2, aircraft: 0.1}
temporal_importance: false
```

## Связанные требования

- BR-FR-060..062 (сбор профиля, нормализация полей, обработка неизвестных полей).
- BR-FR-Data-004 (class priors суммируются к 1.0 ± 1e-6).
- BR-FR-Data-005 (`temporal_importance=true` ⇒ ОБЯЗАНЫ присутствовать `timestamp` + `entity_id`).

## Связанные агенты

- `DataProfilingAgent`, `RAGRetrievalAgent`.

## Связанные контракты

- `DataProfile` (`schemas/agent_outputs.py`).
- Слоты `ContextMemory`: `data_type`, `data_volume`, `fields`, `missing_data_strategy`, `class_distribution`, `temporal_importance`.

## Связанные RAG-документы

- `schema_card` — канонические имена полей, dtype, единицы per `domain`/`data_source`.
- `question_template` — clarification-промпты для отсутствующих слотов профиля.

## Критерии приёмки

- Введённые пользователем `РЛС / radar / ЭПР / RCS` ОБЯЗАНЫ нормализоваться в канонические имена полей через schema-карточки.
- Неизвестное поле ОБЯЗАНО сохраниться как `custom_field` с `requires_review = true`.
- Тест: `tests/component/test_data_profiling_agent.py`.
