# ANALYTICS-03. Дашборд производительности агентов

## Назначение

Per-agent операционный дашборд: число вызовов, latency p50/p95, доля валидного JSON, rate repair-loop, rate `need_more_context`, распределение confidence, использование версии шаблона промпта.

## Бизнес-ценность

Агенты тихо дрейфуют, когда эволюционируют промпты или меняется базовая LLM. Этот дашборд ловит регрессию до того, как она дойдёт до метрик retention.

## Вход и выход

- **Вход.** Логи вызовов runtime-агентов.
- **Выход.** Per-agent число вызовов, latency p50/p95, доля валидного JSON, rate repair-loop, rate `need_more_context`, распределение confidence, использование версий шаблонов промптов.

## Пользовательский сценарий

Архитектор открывает панель для `FeatureSynthesisAgent`: latency p95 = 2.4 с (в цели), JSON-validity = 92 %, rate repair-loop = 7 %, топ-причина сбоя: «derived feature references unknown base». Привязанный drill-down открывает падающие промпты.

## Связанные требования

- BR-Metrics-Agent-001..003 (rate невалидного JSON, count repair-loop, latency p95).
- NFR-Obs-001 (структурированные логи с `agent_name`, `prompt_template_version`, `llm_model`, `llm_latency_ms`, `validation_status`).

## Связанные сервисы

- Agent Runtime, LLM Gateway, Observability Service, Analytics Service, Frontend Agent Dashboard.

## Связанные контракты

- `AgentRunRecord` (`schemas/analytics.py`).

## Критерии приёмки

- Per-agent пользователь ОБЯЗАН видеть как минимум: count, latency p50/p95, JSON-validity rate, repair-loop rate, топ-3 причины сбоев.
- Фильтрация по `prompt_template_version` ОБЯЗАНА работать, чтобы поддерживать A/B-роллауты промптов.
- Тест: `tests/component/test_agent_performance_dashboard.py`.
