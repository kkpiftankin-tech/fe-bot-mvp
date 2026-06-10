# ANALYTICS-01. Дашборд воронки сессий

## Назначение

Показать, как пользователи движутся по Setup и Runtime: количество сессий, rate завершения, среднее время до экспорта, drop-off по фазам, rate ошибок и долю сессий, которые публикуют KB и доходят до Export.

## Бизнес-ценность

Там, где пользователи отваливаются, — там продукт ломается. Без воронки каждая регрессия retention и каждое UX-узкое место остаётся невидимым.

## Пользовательский сценарий

Product-owner открывает Analytics-дашборд, выбирает диапазон дат и видит:

- сессии начатые / завершённые / брошенные,
- медианное wall-clock от `task_discovery` до `export`,
- bar drop-off по фазам,
- топ-5 причин ошибок per-фаза,
- долю сессий, триггернувших `restart`.

## Связанные требования

- BR-Metrics-Conv-001 (≥ 70 % rate завершения).
- BR-Metrics-Slots-001 (≥ 90 % обязательных слотов заполнены корректно).
- BR-Metrics-Time-001 (≤ 15 мин для эталонного сценария).

## Связанные сервисы

- Analytics Service, Frontend Analytics Dashboard, Conversation DB, Event Log Store, API Backend.

## Связанные контракты

- `SessionFunnelEvent` (`schemas/analytics.py`): `session_id`, `phase`, `event_type`, `at`, `error_code`, `error_message`.

## Критерии приёмки

- Дашборд ОБЯЗАН уважать настроенный фильтр диапазона дат.
- Счётчики ОБЯЗАНЫ совпадать с базовым event-store ± 0 (никаких округлений).
- Тест: `tests/component/test_session_funnel_analytics.py`.
