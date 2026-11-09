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

## Входы и выходы системы

Это каноническое описание того, что система принимает и что отдаёт. Другие документы ([vision.md](../01-business/vision.md), [README методологии](../00-methodology/README.md)) приводят только краткую сводку и ссылаются сюда.

### Сводка по стадиям

| Стадия | Что подаёт на вход пользователь | Что система отдаёт на выходе | Кто работает |
| --- | --- | --- | --- |
| **Setup** | Доменные документы (`md`, `txt`, `pdf`, `docx`, `xlsx`, `csv`, `json`), параметры setup job, решения по RAG-карточкам | Опубликованная версия базы знаний (`kb_version`): утверждённые RAG-карточки, чанки, векторный индекс, отчёты проверок, сигнал **«Knowledge Base ready»** | RAG-администратор (на раннем этапе — ML-инженер) |
| **Runtime** | Сообщения на естественном языке (RU/EN): описание задачи, описание данных, ответы на уточняющие вопросы, подтверждения | `archive.zip` из 9 файлов: признаки, `GenerationSpec`, синтетический датасет, `training_config.yaml`, `pipeline.py`, метаданные | ML-инженер / data scientist |
| **Analytics** | События Setup и Runtime (в основном только чтение); для доменного дашборда — агрегаты feature-store из внешних источников | Дашборды качества и сквозной audit trail «исходный документ → экспортированный артефакт» | Product owner, архитектор, аудитор |

Связь стадий: выход Setup (`kb_version`) — обязательное условие входа Runtime. Без опубликованной активной базы знаний Runtime-сессия не стартует ([RUNTIME-01](features/RUNTIME-01-session.md)).

### Чего на входе нет

- **Реальный датасет пользователя в Runtime не загружается.** Профиль данных (имена и типы полей, объём, пропуски, распределение классов, важность времени) пользователь *описывает в диалоге* ([RUNTIME-04](features/RUNTIME-04-data-profiling.md)). Система не читает и не анализирует строки реальных данных.
- **На выходе нет обученной модели.** Система рекомендует модель и отдаёт скрипт `pipeline.py`, который пользователь запускает сам; обучение, хостинг и serving вне scope.
- **Датасет на выходе — синтетический.** Его строит Python-инструмент по `GenerationSpec`, а не LLM и не копирование реальных данных ([RUNTIME-10](features/RUNTIME-10-data-generation.md)).

### Setup: вход

| Что | Детали | Источник |
| --- | --- | --- |
| Файлы документов | `md`, `txt`, `pdf`, `docx`, `xlsx`, `csv`, `json`; дедупликация по SHA-256; максимальный размер по умолчанию 100 МБ; OCR для сканов в MVP нет | [SETUP-02](features/SETUP-02-document-upload.md), [SETUP-01 §4.3](features/SETUP-01-setup-wizard.md), `schemas/common/defaults.py` |
| Параметры setup job | `project_name` (3–128 символов), `domain` (из онтологии или `custom`), `description` (до 2000), `tags`, `embedding_model` (целевой дефолт — 384-мерный sentence-transformer; в коде пока `nomic-embed-text`, 768-мерная — см. [SETUP-09](features/SETUP-09-embeddings-index.md)), `indexing_mode`, `review_policy` (`strict` / `allow_warnings`), `retrieval_test_profile` | [SETUP-01 §13.1](features/SETUP-01-setup-wizard.md) |
| Решения человека | По каждой карточке: `approve` / `reject` / `edit` / `regenerate`; в конце — явное подтверждение публикации | [SETUP-06](features/SETUP-06-rag-card-review.md), [SETUP-11](features/SETUP-11-publish-kb.md) |
| Конфигурация классификации | Дерево классификаторов и их промпты (редактируются в UI, не привязаны к конкретному job) | [SETUP-13](features/SETUP-13-classifier-library.md) (замещает [SETUP-12](features/SETUP-12-llm-taxonomy-classification.md)) |

### Setup: выход

Мастер из 11 шагов; на каждом шаге появляется свой артефакт. Окончательный выход — активная версия базы знаний.

| Шаг мастера | Фича | Что производится |
| --- | --- | --- |
| 1. Создать job | [SETUP-01](features/SETUP-01-setup-wizard.md) | `RAGSetupJob` с `setup_job_id` и статусом |
| 2. Загрузить документы | [SETUP-02](features/SETUP-02-document-upload.md), [SETUP-03](features/SETUP-03-source-registry.md) | Файлы в Object Storage, записи реестра источников (`SourceDocument`: checksum, статус) |
| 3. Парсинг документов | [SETUP-04](features/SETUP-04-document-parsing.md), [SETUP-13](features/SETUP-13-classifier-library.md) | Смысловые секции (`ParsedSection`) с классификацией по дереву классов |
| 4. Генерация RAG-карточек | [SETUP-05](features/SETUP-05-rag-cards-generation.md) | Черновики карточек: YAML-metadata (тип и онтологические поля — из классификации шага 3) + Markdown-тело (LLM) + ссылка на исходную секцию |
| 5. Проверить карточки | [SETUP-06](features/SETUP-06-rag-card-review.md) | Карточки со статусом `approved` / `rejected` (человеческое решение) |
| 6. Валидация metadata | [SETUP-07](features/SETUP-07-metadata-validation.md) | Отчёт валидации; карточки без обязательной metadata не проходят дальше |
| 7. Chunking + индексация | [SETUP-08](features/SETUP-08-chunking.md), [SETUP-09](features/SETUP-09-embeddings-index.md) | Чанки (`chunk_manifest`), embeddings, версионированная коллекция в Qdrant (`index_version`) |
| 8. Retrieval-тесты | [SETUP-10](features/SETUP-10-retrieval-tests.md) | `RetrievalEvalReport`: recall@k, precision@k, no-context rate по контрольным запросам |
| 9. Публикация KB | [SETUP-11](features/SETUP-11-publish-kb.md) | `KnowledgeBaseVersion` в статусе `active`, событие `setup.kb.ready`, сообщение «Knowledge Base ready» |
| 10. Отчёт | [SETUP-01](features/SETUP-01-setup-wizard.md) | `ProcessingReport` по всему job |
| 11. Библиотека классификаторов | [SETUP-13](features/SETUP-13-classifier-library.md) | Редактируемое дерево классов (отдельный от job ресурс) |

**Принцип: смысл секции определяется один раз.** Классификация фрагмента по дереву классов выполняется на шаге 3 и больше нигде не повторяется. Тип карточки и онтологические поля (`domain`, `task_type`, `data_source`, `entity_type`, `phase`, `agent_targets`) шаг 4 выводит детерминированно из metadata-хинтов узлов дерева, а LLM на шаге 4 пишет только содержание карточки; чанки на шаге 7 наследуют metadata карточки. Хинты редактируются вместе с деревом на шаге 11. Ветка дерева без `doc_type_hint` даёт явный отказ секции, а не угаданный тип. Подробности и обоснование — [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md), [SETUP-13 §8](features/SETUP-13-classifier-library.md#8-metadata-хинты-узлов). Это целевой дизайн (см. «Статус реализации»).

Итоговый ответ мастера при успехе ([SETUP-01 §14.1](features/SETUP-01-setup-wizard.md)):

```json
{
  "setup_job_id": "setup_001",
  "status": "ready",
  "knowledge_base_version": "kb_2026_05_19_v1",
  "vector_index_version": "idx_2026_05_19_v1",
  "message": "Knowledge Base ready"
}
```

Публикацию гейтят пороги retrieval-тестов. Временные значения по умолчанию (до решения в ADR-012): `recall@5 ≥ 0.85`, `precision@5 ≥ 0.70`, `no_context_rate ≤ 0.05`; публикация с warning-ами по умолчанию запрещена (`schemas/common/defaults.py`).

### Runtime: вход

Каждый шаг диалога — это сообщение пользователя на естественном языке (русский или английский) плюс `conversation_id`. `NLUAgent` сводит его к одному из закрытого набора intents ([RUNTIME-02](features/RUNTIME-02-nlu.md)). Дополнительно система принимает от пользователя явные решения: подтвердить или изменить набор признаков, принять или заменить рекомендованную модель, запустить генерацию и экспорт.

Что пользователь сообщает и что система из этого строит, по фазам:

| # | Фаза | Что даёт пользователь | Что фиксируется в `ContextMemory` |
| --- | --- | --- | --- |
| 0 | `initialization` | Нажимает **Start project** | `conversation_id`, `kb_version` (активная база знаний), `current_phase` |
| 1 | `task_discovery` | Формулировка задачи («Нужен классификатор типа морской цели по данным РЛС»), ответы на уточнения (например, список классов) | `task_type`, `target_variable`, `classes`, `domain`, `data_source` |
| 2 | `data_profiling` | Описание данных: объём, поля (имя, тип, единицы), пропуски, распределение классов, важна ли временная ось | `data_volume`, `data_type`, `fields`, `missing_data_strategy`, `class_distribution`, `temporal_importance` |
| 3 | `domain_context` | Подтверждает или правит предложенные критичные факторы и требование к интерпретируемости | `critical_factors`, `interpretability_requirement`, `evidence_pack` |
| 4 | `feature_synthesis` | Ревьюит набор признаков: **Confirm** / **Remove** / **Add** / **Explain** / **Back to Data Profiling** | `base_features`, `derived_features`, `interaction_features`, `final_features` |
| 5 | `data_generation` | Нажимает **Generate dataset** | `generation_spec`, `generated_dataset` |
| 6 | `model_selection` | Принимает первую рекомендацию или делает **Override** | `recommended_model`, `model_ranking`, `training_config` |
| 7 | `export` | Нажимает **Export project** | `artifacts`, `export_manifest` |

Фаз в `ContextMemory` восемь: `initialization` плюс семь пользовательских фаз (в UI показывается 7-фазный прогресс).

### Runtime: выход

Единственное, что пользователь уносит из диалога, — `archive.zip` с time-bound ссылкой скачивания ([RUNTIME-12](features/RUNTIME-12-export.md), [PLATFORM-04](features/PLATFORM-04-artifact-storage.md)):

| Файл | Что внутри | Формат | Откуда содержимое |
| --- | --- | --- | --- |
| `features.json` | Подтверждённые признаки (`FeatureSpec[]`): формула, `input_features`, `evidence_doc_ids` | JSON | `FeatureSynthesisAgent` + валидаторы + решение пользователя |
| `generation_spec.json` | `GenerationSpec`: `random_state`, `n_samples`, распределения признаков, шум, аномалии | JSON | `DataGenerationSpecAgent` |
| `X_train.csv` | Синтетическая матрица признаков (эталон: 100 000 × 19) | CSV | `DataGenerationWorker` (Python, без LLM) |
| `y_train.npy` | Метки классов | NumPy | `DataGenerationWorker` |
| `training_config.yaml` | Модель, гиперпараметры, стратегия CV, метрики, `class_weight` | YAML | `ModelSelectionAgent` |
| `pipeline.py` | Запускаемый скрипт обучения (класс `MLPipeline`: `load_data`, `preprocess`, `train`, `evaluate`, `predict`, `save_model`); зависит только от `pandas`, `numpy`, `scikit-learn`, `xgboost` | Python | Export Service (сериализует подтверждённое состояние) |
| `data_generator.py` | Воспроизводимый генератор датасета | Python | Export Service |
| `metadata.json` | Происхождение: `conversation_id`, версии схем и промптов, id LLM- и embedding-моделей, версия KB, digests датасета | JSON | Export Service |
| `validation_report.json` | Результаты детерминированных валидаторов | JSON | `ValidationWorker` |

Что гарантирует выход:

- у каждого признака есть `evidence_doc_ids` — ссылки на карточки базы знаний;
- повторная генерация с тем же `GenerationSpec` и `random_state` даёт байт-идентичный датасет;
- пакет запускается локально без FE-Bot: `python data_generator.py && python pipeline.py --config training_config.yaml`;
- для любого артефакта в audit trail прослеживается путь до исходного документа Setup.

### Analytics: вход и выход

Вход — события, которые уже эмитируют Setup и Runtime; для доменного дашборда ([ANALYTICS-08](features/ANALYTICS-08-domain-feature-store.md)) — ещё и агрегаты feature-store из внешних источников. Стадия в основном read-only; исключение — curation RAG-карточек в [ANALYTICS-04](features/ANALYTICS-04-rag-content-lifecycle.md). Выход — девять представлений (ANALYTICS-01..09), включая сквозной audit trail; список — в разделе «Стадия 3 — Analytics» ниже.

### Пример на эталонном домене

| Этап | Вход | Выход |
| --- | --- | --- |
| Setup | Папка Markdown/PDF-документов по морской радиолокации | Активная `kb_version` с карточками `schema`, `task`, `analytics`, `feature_pattern`, `validation_rule`, `question_template`; сообщение «Knowledge Base ready» |
| Runtime, фазы 1–3 | «Нужен классификатор типа морской цели по данным РЛС»; классы `civilian_ship`, `military_ship`, `submarine`, `aircraft`; поля `range`, `azimuth`, `elevation`, `rcs`, `snr`, `doppler`; priors `[0.4, 0.3, 0.2, 0.1]` | `ContextMemory` с типизированным профилем задачи и данных, доменные критичные факторы |
| Runtime, фаза 4 | Подтверждение набора признаков | 19 признаков (6 базовых + 8 производных + 5 interaction), каждый с `evidence_doc_ids` |
| Runtime, фазы 5–6 | Запуск генерации, принятие рекомендации модели | Датасет 100 000 × 19; `XGBoostClassifier`, метрика `f1_macro`, stratified 5-fold CV |
| Runtime, фаза 7 | Запуск экспорта | `archive.zip` (9 файлов) |
| Analytics | — | Новая сессия в дашборде, retrieval hit rate, latency агентов, трасса от документов до архива |

## Стадия 1 — Setup (мастер базы знаний)

Пользовательский мастер, который производит валидированную retrievable базу знаний. Принадлежит **Setup Orchestrator**; запускается один раз на версию базы знаний плюс при каждом повторном ingestion новых документов.

Этапы Setup и владеющие ими сервисы (шаги мастера и их артефакты — в таблице «Setup: выход» выше):

| # | Этап | Владеющий сервис | Выход |
| --- | --- | --- | --- |
| 1 | Загрузка документов | Document Ingestion Service | строки реестра source_document |
| 2 | Парсинг и классификация секций | Document Parser (классификация — [SETUP-13](features/SETUP-13-classifier-library.md)) | parsed_sections с классами |
| 3 | Генерация RAG-карточек | RAG Card Generator | черновики карточек (schema / task / analytics / feature pattern / validation / question template) |
| 4 | Ревью карточек (HITL) | Card Review UI | approved-карточки |
| 5 | Валидация metadata | Metadata Validator | validation report |
| 6 | Чанкование | Chunking Service | chunk manifest |
| 7 | Embeddings и индексация | Embedding Service + Vector DB Indexer | версия векторного индекса |
| 8 | Retrieval smoke-тесты | RAG Evaluation Service | retrieval report |
| 9 | Публикация | Knowledge Base Registry | активная версия KB + уведомление "ready" |

Подробные фичи: [features/feature-index.md](features/feature-index.md) — SETUP-01..SETUP-13 (SETUP-12 замещена SETUP-13).

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

Компоненты, от которых зависят все три стадии (PLATFORM-01..PLATFORM-05):

- **API Backend** — единая HTTP-поверхность для UI, агентов, оркестрации Setup, runtime, analytics, export.
- **LangGraph Orchestrator** — мультиагентный workflow с явной state machine, repair-loops, HITL.
- **Structured Output Contracts** — Pydantic-схемы, валидаторы, repair-промпты; каждый вывод LLM через них проходит.
- **Artifact Storage + Download Manager** — хранилище на MinIO с per-conversation scoping.
- **RAG Retrieval + Evidence Pack** — единственный путь агентов к базе знаний: metadata-фильтры, поиск в Vector DB, компактный `EvidencePack` ([PLATFORM-05](features/PLATFORM-05-rag-retrieval.md)).

## Статус реализации

Состояние на 2026-11-05 (проверено по содержимому репозитория; статусы отдельных фич — в [feature-index.md](features/feature-index.md)):

| Стадия | Что есть в коде | Чего ещё нет |
| --- | --- | --- |
| Setup | Backend `src/fe_bot/setup/`, API `src/fe_bot/api/setup/`, Pydantic-схемы `schemas/setup/`, `schemas/rag/`, UI мастера `frontend/src/components/Wizard/` | — |
| Runtime | Только документация: [../05-agents/](../05-agents/), [../07-contracts/](../07-contracts/), [../09-langgraph/](../09-langgraph/) | Пакеты `src/fe_bot/agents/`, `src/fe_bot/graph/`, `src/fe_bot/data_generation/`, `src/fe_bot/export/` пусты; схем `ContextMemory` и агентных выводов в `schemas/` пока нет |
| Analytics | Заготовки наблюдаемости и аудита (`src/fe_bot/observability/`, `src/fe_bot/audit/`) | Дашборды |

Следствие: описание Runtime и Analytics в этом разделе — **целевое поведение**, а не описание работающего кода.

Внутри Setup есть одно известное расхождение с дизайном: шаг 4 пока не использует результат классификации шага 3 и определяет тип карточки и онтологические поля повторно (по `section_type` и LLM-промптом). Принятое решение — [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md), расхождение — [TD-HTC-004](../tech-debt/TD-HTC-004-duplicate-classification-in-card-generation.md).

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
- Загрузка и анализ реальных датасетов пользователя в Runtime (профиль данных собирается из диалога).

## Связанные документы

- [actors.md](actors.md)
- [functional-requirements.md](functional-requirements.md)
- [non-functional-requirements.md](non-functional-requirements.md)
- [features/feature-index.md](features/feature-index.md)
- [../01-business/vision.md](../01-business/vision.md)
