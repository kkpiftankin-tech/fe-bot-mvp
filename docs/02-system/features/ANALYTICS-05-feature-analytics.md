# ANALYTICS-05. Аналитика генерации признаков

## Назначение

Показать распределение предложенных vs. принятых vs. отвергнутых признаков, топ-причины отклонения, популярные семейства признаков, счётчики признаков per-сессия, покрытие evidence и распределение risk-level.

## Бизнес-ценность

Если 60 % предложенных признаков отвергаются по одной и той же причине — это баг промпта или покрытия карточек, и он должен быть очевиден на одном графике.

## Пользовательский сценарий

Data scientist открывает панель: 73 % rate приёмки за последний месяц; топ-причина отклонения «missing evidence_doc_ids» (триггерит фикс в SETUP-05); распределение feature-family показывает недопокрытие карточек `signal_quality` для naval-домена.

## Связанные требования

- BR-Metrics-Feature-001..003 (rate приёмки, покрытие evidence, распределение семейств).
- BR-FR-Feature-004 (каждый approved-признак ОБЯЗАН цитировать evidence).

## Связанные сервисы

- Feature Analytics Service, логи Feature Synthesis Agent, Validation Service, Frontend Feature Analytics Dashboard, Conversation DB.

## Связанные контракты

- `FeatureGenerationEvent` (`schemas/analytics.py`): `session_id`, `feature_id`, `role`, `decision`, `decision_reason`, `evidence_doc_ids`.

## Критерии приёмки

- Пользователь ОБЯЗАН иметь возможность срезать по `domain`, `task_type`, `data_source`.
- Доля «no-evidence»-признаков выше 10 % ОБЯЗАНА поднимать soft-warning на дашборде.
- Тест: `tests/component/test_feature_analytics_dashboard.py`.
