# System Overview

Птичий вид FE-Bot. За деталями переходите в [features/](features/), [use-cases/](use-cases/), [../03-architecture/](../03-architecture/) и [../05-agents/](../05-agents/).

## Однострочное описание

FE-Bot — трёхстадийная мультиагентная платформа: **Setup** строит типизированную базу знаний из сырых документов, **Runtime** превращает описание ML-задачи в воспроизводимый пакет обучения, **Analytics** обнажает сигналы качества по обеим стадиям.

## Три стадии

```text
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Стадия 1       │    │   Стадия 2       │    │   Стадия 3       │
│   SETUP          │───▶│   RUNTIME        │───▶│   ANALYTICS      │
│   (мастер-UI)    │    │   (чат-UI)       │    │   (дашборды)     │
│                  │    │                  │    │                  │
│ сырые docs →     │    │ задача →         │    │ воронки сессий   │
│ RAG-карточки →   │    │ ContextMemory →  │    │ качество RAG     │
│ embeddings →     │    │ признаки →       │    │ latency агентов  │
│ vector index →   │    │ синт. данные →   │    │ исходы признаков │
│ KB опубликована  │    │ модель + export  │    │ audit trail      │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

У каждой стадии свой UI, своя метрика успеха и свой срез data-модели. База знаний, построенная на Стадии 1, — это то, из чего читает Стадия 2. События, эмитируемые Стадиями 1 и 2, — это то, по чему отчитывается Стадия 3.

## Стадия 1 — Setup (мастер базы знаний)

Пользовательский мастер, который производит валидированную retrievable базу знаний. Принадлежит **Setup Orchestrator**; запускается один раз на версию базы знаний плюс при каждом повторном ingestion новых документов.

Фазы внутри Setup:

| # | Фаза | Владеющий сервис | Выход |
| --- | --- | --- | --- |
| 1 | Загрузка документов | Document Ingestion Service | строки реестра source_document |
| 2 | Парсинг и извлечение секций | Document Parser | parsed_sections |
| 3 | Генерация RAG-карточек | RAG Card Generator | черновики карточек (schema / task / analytics / feature pattern / validation / question template) |
| 4 | Ревью карточек (HITL) | Card Review UI | approved-карточки |
| 5 | Валидация metadata | Metadata Validator | validation report |
| 6 | Чанкование | Chunking Service | chunk manifest |
| 7 | Embeddings и индексация | Embedding Service + Vector DB Indexer | версия векторного индекса |
| 8 | Retrieval smoke-тесты | RAG Evaluation Service | retrieval report |
| 9 | Публикация | Knowledge Base Registry | активная версия KB + уведомление "ready" |

Подробные фичи: [features/feature-index.md](features/feature-index.md) — SETUP-01..SETUP-11.

## Стадия 2 — Runtime (диалог ML-задачи)

Управляемый мультиагентный диалог. Принадлежит **LangGraph Orchestrator**.

| # | Фаза | Основные агенты | Пишет в ContextMemory |
| --- | --- | --- | --- |
| 0 | `initialization` | `SessionAgent` | `conversation_id`, `current_phase`, `user_request` |
| 1 | `task_discovery` | `NLUAgent`, `TaskDiscoveryAgent` | `task_type`, `target_variable`, `domain`, `data_source` |
| 2 | `data_profiling` | `DataProfilingAgent` | `data_type`, `data_volume`, `fields`, `missing_data_strategy`, `class_distribution`, `temporal_importance` |
| 3 | `domain_context` | `DomainContextAgent`, `RAGRetrievalAgent` | `critical_factors`, `interpretability_requirement`, `evidence_pack` |
| 4 | `feature_synthesis` | `FeatureSynthesisAgent`, `FeatureCriticAgent`, `MulticollinearityAgent` | `base_features`, `derived_features`, `interaction_features`, `final_features` |
| 5 | `data_generation` | `DataGenerationSpecAgent`, `DataGenerationWorker` | `generation_spec`, `generated_dataset` |
| 6 | `model_selection` | `ModelSelectionAgent` | `recommended_model`, `model_ranking`, `training_config` |
| 7 | `export` | `ExportAgent` | `artifacts`, `export_manifest` |

Подробные фичи: RUNTIME-01..RUNTIME-12. Подробные спецификации агентов: [../05-agents/](../05-agents/).

## Стадия 3 — Analytics

Дашборды и audit trails, читающие события Setup + Runtime.

| Дашборд | Читает из | Назначение |
| --- | --- | --- |
| Воронка сессий | Conversation DB, Event Log | drop-off по фазам, время до экспорта |
| Качество RAG | Логи retrieval, eval-прогоны | recall@k, precision@k, no-context rate, неиспользованные docs |
| Производительность агентов | Логи runtime агентов | latency, rate repair-loop, доля валидного JSON |
| Жизненный цикл RAG-контента | RAG Card Registry, usage logs | устаревшие / неиспользуемые / low-confidence карточки |
| Исходы признаков | Логи Feature Synthesis, validation-отчёты | rate приёмки, причины отклонения |
| Качество синтетических данных | Валидаторы датасета | здоровье shape / NaN / class-balance |
| Рекомендации моделей | Логи Model Selection | recommended vs. selected, override rate |
| Доменный feature store | Агрегаты по sensor / object / environment | аналитика по работающему домену |
| Audit trail | Audit Service | цепочка от исходного документа до экспортированного артефакта |

Подробные фичи: ANALYTICS-01..ANALYTICS-09.

## Сквозная платформа

Компоненты, от которых зависят все три стадии (PLATFORM-01..PLATFORM-04):

- **API Backend** — единая HTTP-поверхность для UI, агентов, оркестрации Setup, runtime, analytics, export.
- **LangGraph Orchestrator** — мультиагентный workflow с явной state machine, repair-loops, HITL.
- **Structured Output Contracts** — Pydantic-схемы, валидаторы, repair-промпты; каждый вывод LLM через них проходит.
- **Artifact Storage + Download Manager** — хранилище на MinIO с per-conversation scoping.

## Входы и выходы (Runtime)

```text
Входы
  └─ Диалог пользователя (естественный язык)
  └─ Опционально: резюме сэмпла данных
  └─ Опционально: подсказка по домену

Выходы (в archive.zip)
  ├─ features.json            (FeatureSpec[])
  ├─ generation_spec.json     (GenerationSpec)
  ├─ X_train.csv              (синтетический датасет)
  ├─ y_train.npy              (метки)
  ├─ training_config.yaml     (модель + CV + метрики)
  ├─ pipeline.py              (запускаемый training-скрипт)
  ├─ data_generator.py        (воспроизводимый генератор данных)
  ├─ metadata.json            (provenance, hashes, versions)
  └─ validation_report.json
```

## Ключевые качества (из [non-functional-requirements.md](non-functional-requirements.md))

- **Дружелюбие к маленькой LLM.** Дефолт `llama3.2:latest` через локальный Ollama, класс 1B–3B; узкие промпты, каждый выход валидируется.
- **Local-first.** Полный стек на ноутбуке через Docker Compose; никаких облачных зависимостей в дефолтном пути.
- **Воспроизводимость.** `random_state` в каждом `GenerationSpec`; metadata-hash фиксируется.
- **Инспектируемость.** У каждого артефакта есть trace через `evidence_doc_ids`, валидаторы и audit trail.

## Эталонный домен (бегущий пример: naval / radar)

Используется в документации как конкретный пример. Классы: `civilian_ship`, `military_ship`, `submarine`, `aircraft`. Поля: `range, azimuth, elevation, rcs, snr, doppler`. Целевое число признаков для happy path: 6 базовых + 8 производных + 5 interaction = 19. Class priors: `[0.4, 0.3, 0.2, 0.1]`. Синтетический датасет: 100k строк × 19 столбцов. Рекомендованная модель: `XGBoostClassifier` с `f1_macro` и stratified 5-fold CV.

## Вне scope

- Production-обучение, хостинг или serving моделей.
- Real-time / streaming inference.
- Разделение памяти между диалогами.
- Автономные циклы переобучения.

## Связанные документы

- [actors.md](actors.md)
- [functional-requirements.md](functional-requirements.md)
- [non-functional-requirements.md](non-functional-requirements.md)
- [features/feature-index.md](features/feature-index.md)
