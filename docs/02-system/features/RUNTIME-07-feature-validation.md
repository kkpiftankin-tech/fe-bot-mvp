# RUNTIME-07. Feature Validation

## Назначение

Детерминированно проверить каждый кандидатный признак против каталога полей, парсера формул, временных ограничений, требований к evidence, порогов мультиколлинеарности и validation-rule-карточек в базе знаний. Эмитнуть `ValidationReport` с per-feature `passed | rejected | warning | needs_review`.

## Бизнес-ценность

Предложенные LLM признаки могут ссылаться на несуществующие поля, изобретать временные lookback-ы, дублировать друг друга или нарушать доменные правила. Валидация — то, что делает опубликованный набор признаков безопасным для использования ниже.

## Пользовательский сценарий

Per-признак пользователь видит status-бейдж с обоснованием: *«`range_acceleration` rejected: requires temporal sequence but `temporal_importance=false`»*. Пользователь чинит upstream-профиль, удаляет признак или добавляет обоснование и перезапускает валидацию.

## Связанные требования

- BR-FR-Feature-005 (каждый approved-признак проходит валидаторы).
- BR-FR-Feature-006..007 (ограничения для временных признаков, существование input-features).
- Мультиколлинеарность: признаки с `|ρ| ≥ 0.95` или `VIF ≥ 10` помечаются. Лимиты: `MAX_FEATURES = 200`, `MAX_INTERACTIONS = 50`.

## Связанные агенты

- `FeatureCriticAgent`, `MulticollinearityAgent`.

## Связанные сервисы

- Validation Service, ValidationWorker, ContextMemory Service, Frontend Validation Panel.

## Связанные контракты

- `ValidationReport` (`schemas/validation_report.py`) — см. [../../07-contracts/validation-report.md](../../07-contracts/validation-report.md).
- Валидатор: [`validators/feature_validator.py`](../../../validators/feature_validator.py).

## Связанные RAG-документы

- `validation_rule`-карточки, отфильтрованные по `task_type` × `domain`.

## Критерии приёмки

- Признак, помеченный `rejected`, НЕ ОБЯЗАН попадать в `final_features`.
- Признак с высокой парной корреляцией ОБЯЗАН быть помечен с именем конфликтующего.
- Лимиты по признакам ОБЯЗАНЫ форситься строго; пользователь не может их обойти через UI.
- Тесты: `tests/unit/test_feature_validator.py`, `tests/component/test_feature_critic_agent.py`.
