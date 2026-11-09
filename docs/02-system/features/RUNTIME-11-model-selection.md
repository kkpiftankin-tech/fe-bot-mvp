# RUNTIME-11. Выбор модели

## Назначение

Рекомендовать ранжированный список ML-моделей с обоснованиями и эмитнуть `training_config` (preprocessing, гиперпараметры, стратегия CV, метрики, early stopping), который потребит экспорт-пакет.

## Бизнес-ценность

Пользователь получает обоснованную стартовую точку — не случайную модель — и запускаемый config, согласованный с типом задачи, формой данных, требованиями к интерпретируемости и latency.

## Вход и выход

- **Вход.** `ContextMemory` (задача, данные, `final_features`), `EvidencePack` и решение пользователя — принять рекомендацию или **Override**.
- **Выход.** `ModelRecommendation` (ранжированный список моделей с обоснованиями) и `training_config` (preprocessing, гиперпараметры, стратегия CV, метрики).

## Пользовательский сценарий

Для эталонного radar-сценария агент эмитит top-3:

1. `XGBoostClassifier` — сильный baseline для табличной мультиклассовой; поддерживает feature importance.
2. `RandomForestClassifier` — устойчивый + интерпретируемый.
3. `BayesianNetwork` — высокая интерпретируемость для операторских решений.

Пользователь принимает дефолт или переопределяет; система пишет `training_config.yaml` с `f1_macro`, `balanced_accuracy`, stratified 5-fold CV, `class_weight: balanced`, `random_state: 42`.

## Связанные требования

- BR-FR-Model-001..002 (ранжированная рекомендация, training config).
- BR-FR-100 (рекомендация top-N моделей по типу задачи, домену, типу данных, числу признаков и классов, интерпретируемости, RAG-рекомендациям).
- BR-FR-101..103 (поддерживаемые семейства моделей per task type, обоснование, форма training-config).
- Дефолтные поддерживаемые модели: XGBoost, LightGBM, RandomForest, SVM, простая нейросеть (классификация); ElasticNet / linear / GBM (регрессия); KMeans / DBSCAN / GMM (кластеризация); IsolationForest / OneClassSVM / Autoencoder (аномалии); learning-to-rank GBM-ы (ranking).

## Связанные агенты

- `ModelSelectionAgent`, `RAGRetrievalAgent`.

## Связанные контракты

- `ModelRecommendation`, `TrainingConfig` (`schemas/model_recommendation.py`).

## Связанные RAG-документы

- `model_recommendation`-карточки, ключованные по `task_type` × `data_type` × `interpretability_requirement`.

## Критерии приёмки

- Top-1 рекомендация ОБЯЗАНА быть согласована с `task_type`, `data_type`, `data_volume`, `interpretability_requirement` и `required_latency`.
- Переопределение пользователем ОБЯЗАНО уважаться и фиксироваться в audit trail.
- Эмитированный `training_config` ОБЯЗАН валидироваться против `TrainingConfig` и проходить `tests/unit/test_training_config_schema.py`.
- Тест: `tests/component/test_model_selection_agent.py`.
