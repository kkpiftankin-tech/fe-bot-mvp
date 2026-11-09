# ANALYTICS-06. Качество синтетических датасетов

## Назначение

Per-датасет отчёт о качестве: shape, count NaN/Inf, запрошенное vs. фактическое распределение классов, фактический anomaly rate, per-feature drift распределения против spec, status валидации.

## Бизнес-ценность

Событие «датасет сгенерирован» не равно «датасет пригоден». Этот дашборд делает это различие видимым.

## Вход и выход

- **Вход.** Отчёты валидаторов по сгенерированным датасетам.
- **Выход.** Per-датасет отчёт: shape, число NaN/Inf, запрошенное vs. фактическое распределение классов, фактический anomaly rate, drift распределений против spec, статус валидации.

## Пользовательский сценарий

ML-инженер открывает отчёт для `conv_abc123`: shape `100000 × 19` ✅, нет NaN ✅, class priors в 0.2 % ✅, фактический anomaly rate 0.021 (запрошено 0.02) ✅, KS-stat распределения `range` = 0.01 ✅. Итог: green; нижестоящий Export может идти.

## Связанные требования

- BR-FR-Gen-003 (валидация: shape, NaN, Inf, классы, anomaly rate).
- BR-Metrics-Dataset-001..003 (validity rate, drift-сигналы, соответствие anomaly).

## Связанные сервисы

- Synthetic Data Validation Worker, Analytics Service, Artifact Storage, Frontend Dataset Quality Dashboard.

## Связанные контракты

- `DatasetQualityReport` (`schemas/analytics.py`).

## Критерии приёмки

- Падающая валидация ОБЯЗАНА проявляться красным на дашборде с конкретным именем проверки.
- Отчёт ОБЯЗАН ссылаться напрямую на исходные `metadata.json` и `validation_report.json`.
- Тест: `tests/component/test_dataset_quality_dashboard.py`.
