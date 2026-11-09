# Функциональные требования

У каждого требования есть стабильный ID `FR-<Area>-<NN>`. Области:

- `Conv` — обработка диалога
- `Task` — discovery задачи
- `Data` — профилирование данных
- `Domain` — доменный контекст
- `RAG` — retrieval
- `Feature` — синтез признаков
- `Gen` — генерация данных
- `Model` — выбор модели
- `Export` — экспорт
- `Sys` — сквозное поведение системы

У каждого FR есть хотя бы одна фича в [features/](features/) и хотя бы один тест в [../../tests/](../../tests/).

## Область действия документа

Требования ниже описывают **Runtime** (стадию 2) и сквозное поведение системы. Требования двух других стадий живут в файлах фич:

- **Setup** — `BR-FR-Setup-*` в разделах «Связанные требования» файлов [SETUP-01..SETUP-13](features/feature-index.md) (загрузка и валидация файлов, парсинг, генерация и ревью карточек, чанкование, индексация, публикация);
- **Analytics** — критерии приёмки файлов [ANALYTICS-01..ANALYTICS-09](features/feature-index.md).

Что система принимает и отдаёт — в [system-overview.md](system-overview.md#входы-и-выходы-системы).

## Conversation (Conv)

- **FR-Conv-001.** Система ОБЯЗАНА принимать свободный текст и `conversation_id` через HTTP-эндпоинт.
- **FR-Conv-002.** Система ОБЯЗАНА загружать и сохранять `ContextMemory` для данного `conversation_id` между шагами.
- **FR-Conv-003.** Система ОБЯЗАНА возвращать следующий промпт агента или требуемый уточняющий вопрос после каждого шага.
- **FR-Conv-004.** Система ОБЯЗАНА не хранить состояние агента только в истории чата; `ContextMemory` — источник истины.
- **FR-Conv-005.** Система ОБЯЗАНА переходить к следующей фазе только после выполнения completion criteria текущей фазы; при одной и той же `ContextMemory` переход ОБЯЗАН быть детерминированным. Зеркалит `BR-FR-031`.
- **FR-Conv-006.** Система ОБЯЗАНА позволять пользователю до экспорта вернуться к ранее пройденной фазе и изменить целевую переменную, источник данных, поля, домен, требование к интерпретируемости, число признаков, размер выборки, модель или формат экспорта; при возврате зависимые (downstream) слоты `ContextMemory` ОБЯЗАНЫ инвалидироваться. Зеркалит `BR-FR-032`.

## Task Discovery (Task)

- **FR-Task-001.** Система ОБЯЗАНА извлекать `task_type` ∈ {classification, regression, clustering, anomaly_detection, ranking} из запроса (то же множество — в [RUNTIME-03](features/RUNTIME-03-task-discovery.md) и `ContextMemory`).
- **FR-Task-002.** Система ОБЯЗАНА извлекать или запрашивать `target_variable` и (для классификации) `classes`.
- **FR-Task-003.** Система ОБЯЗАНА извлекать или запрашивать `domain` и `data_source`.
- **FR-Task-004.** Когда поля задачи не могут быть выведены, система ОБЯЗАНА задать целевой уточняющий вопрос, а не угадывать.

## Data Profiling (Data)

- **FR-Data-001.** Система ОБЯЗАНА собирать `data_volume` (число строк) и `data_type` ∈ {tabular, time_series, image, tensor, graph, event_log, mixed}. Генерация синтетических данных в MVP поддерживает только `tabular` ([RUNTIME-10](features/RUNTIME-10-data-generation.md)).
- **FR-Data-002.** Система ОБЯЗАНА перечислять `fields` с `name`, `dtype`, и опционально `unit`, `role`.
- **FR-Data-003.** Система ОБЯЗАНА захватывать `missing_data_strategy` ∈ {drop, fill_zero, fill_mean, fill_median, forward_fill, none}.
- **FR-Data-004.** Для классификации система ОБЯЗАНА захватывать `class_distribution`, чьи приоры суммируются к 1.0 ± tolerance.
- **FR-Data-005.** Система ОБЯЗАНА захватывать `temporal_importance` (bool) и требовать поля `timestamp` и `entity_id`, когда `true`.

## Domain Context (Domain)

- **FR-Domain-001.** Система ОБЯЗАНА извлекать `critical_factors` для выбранного домена через RAG-подкреплённое рассуждение.
- **FR-Domain-002.** Система ОБЯЗАНА захватывать `interpretability_requirement` ∈ {high, medium, low}.

## Retrieval (RAG)

- **FR-RAG-001.** Система ОБЯЗАНА извлекать только карточки, чья metadata соответствует текущим фильтрам `phase`, `domain`, `data_source` и `task_type`.
- **FR-RAG-002.** Каждый вызов retrieval ОБЯЗАН планироваться `RAGQueryPlannerAgent`-ом против [../06-rag/retrieval-policies.md](../06-rag/retrieval-policies.md).
- **FR-RAG-003.** Агенты ОБЯЗАНЫ потреблять `EvidencePack`, а не сырые retrieval-результаты.
- **FR-RAG-004.** Каждая возвращённая карточка ОБЯЗАНА иметь валидированную metadata (см. [../06-rag/metadata-schema.md](../06-rag/metadata-schema.md)).

## Feature Synthesis (Feature)

- **FR-Feature-001.** Система ОБЯЗАНА предлагать `base_features`, взятые из `ContextMemory.fields`.
- **FR-Feature-002.** Система ОБЯЗАНА предлагать `derived_features` с `formula` и `input_features`.
- **FR-Feature-003.** Система ОБЯЗАНА предлагать `interaction_features`, где доменные evidence их поддерживают.
- **FR-Feature-004.** Каждый `approved`-признак ОБЯЗАН цитировать непустые `evidence_doc_ids`.
- **FR-Feature-005.** Каждый признак ОБЯЗАН пройти `FeatureCriticAgent` и детерминированные валидаторы до попадания в `final_features`.
- **FR-Feature-006.** Временные признаки НЕ ОБЯЗАНЫ предлагаться, когда `temporal_importance=false`.
- **FR-Feature-007.** Производные признаки ОБЯЗАНЫ ссылаться только на `input_features`, существующие в `ContextMemory.fields` или среди ранее принятых признаков.

## Data Generation (Gen)

- **FR-Gen-001.** Система ОБЯЗАНА производить `GenerationSpec` с `random_state`, `n_samples`, target и per-feature распределениями.
- **FR-Gen-002.** Синтетический датасет ОБЯЗАН генерироваться `DataGenerationWorker`-ом (Python), никогда — токенами LLM.
- **FR-Gen-003.** Сгенерированный датасет ОБЯЗАН проходить `generated_data_validator` (нет NaN/inf, где `missing_data_strategy=none`, баланс классов в допуске, соответствие схеме).
- **FR-Gen-004.** Повторная генерация с тем же `GenerationSpec` ОБЯЗАНА производить байт-идентичный датасет (с точностью до timestamps).

## Model Selection (Model)

- **FR-Model-001.** Система ОБЯЗАНА рекомендовать `recommended_model` и top-N `model_ranking`, согласованные с `task_type`, `data_type` и `data_volume`.
- **FR-Model-002.** Система ОБЯЗАНА производить `training_config` с `metrics`, `validation` и `class_weight`, подходящими `class_distribution`.

## Export (Export)

- **FR-Export-001.** Система ОБЯЗАНА собирать `archive.zip`, содержащий артефакты из [system-overview.md](system-overview.md).
- **FR-Export-002.** `metadata.json` ОБЯЗАН включать `conversation_id`, версии схем, хэши моделей и digest сгенерированного датасета.
- **FR-Export-003.** Артефакты ОБЯЗАНЫ быть адресуемы через `ExportManifest`.

## Сквозные (Sys)

- **FR-Sys-001.** Каждый агентный вывод ОБЯЗАН быть валидирован против Pydantic-схемы до записи в `ContextMemory`.
- **FR-Sys-002.** Repair-петли ОБЯЗАНЫ быть ограничены `max_retries` (по умолчанию 3).
- **FR-Sys-003.** Система ОБЯЗАНА эмитить структурированные логи с `conversation_id`, `agent_name`, `phase`, `node_name`, `trace_id`.
- **FR-Sys-004.** Система ОБЯЗАНА выставлять метрики, перечисленные в [../11-operations/metrics.md](../11-operations/metrics.md).

## Traceability

См. [../traceability/requirements-to-tests.md](../traceability/requirements-to-tests.md) для маппинга FR → тест.
