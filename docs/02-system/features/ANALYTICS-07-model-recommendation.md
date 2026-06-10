# ANALYTICS-07. Аналитика рекомендаций моделей

## Назначение

Показать, что система рекомендовала vs. что выбрал пользователь: распределение моделей per-`task_type` × `data_type`, rate переопределения пользователем, топ-причины переопределения, сбои валидации training-config.

## Бизнес-ценность

Когда пользователи систематически переопределяют top-1 рекомендацию — это сигнал: эвристики ранжирования или базовые RAG-карточки требуют работы.

## Пользовательский сценарий

Product-owner видит, что `BayesianNetwork` рекомендуется top-1 в 18 % сессий с высокой interpretability, но выбирается лишь в 5 % — drill-down показывает, что пользователи выбирают `XGBoost + SHAP`, потому что быстрее в deploy. Команда обновляет веса deployment-context в карточках model_recommendation.

## Связанные требования

- BR-Metrics-Model-001..003 (распределение рекомендаций, rate переопределения, причины переопределения).

## Связанные сервисы

- Логи Model Selection Agent, Analytics Service, Frontend Model Analytics Dashboard, ContextMemory Service.

## Связанные контракты

- `ModelRecommendationEvent` (`schemas/analytics.py`): `session_id`, `recommended_top1`, `selected_model`, `override_reason`, `interpretability_requirement`.

## Критерии приёмки

- Пользователь ОБЯЗАН иметь возможность фильтровать по `task_type`, `data_type`, `interpretability_requirement`, `deployment_context`.
- Rate переопределения выше 30 % для модели ОБЯЗАН поднимать soft-warning на дашборде.
- Тест: `tests/component/test_model_recommendation_dashboard.py`.
