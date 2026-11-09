# Индекс фич

Системные фичи, сгруппированные по стадии. ID стадий зеркалят project backlog: `SETUP-XX`, `RUNTIME-XX`, `ANALYTICS-XX`, `PLATFORM-XX`. У каждой фичи свой файл в этом каталоге со ссылками на требования, агентов, контракты, RAG-документы и критерии приёмки.

Колонки «Вход» и «Выход» — краткая сводка; точные контракты — в файле фичи. Сквозное описание входов и выходов системы — в [../system-overview.md](../system-overview.md#входы-и-выходы-системы).

Колонка «Статус» описывает состояние **документа** фичи. Состояние реализации в коде — в [../system-overview.md](../system-overview.md#статус-реализации).

## Стадия 1 — Setup (мастер базы знаний)

Фичи идут в порядке шагов мастера; шаг 3 «Парсинг» включает классификацию секций. Активный классификатор — [SETUP-13](SETUP-13-classifier-library.md); [SETUP-12](SETUP-12-llm-taxonomy-classification.md) им замещена ([ADR-HTC-09](../../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)), но её код сохранён.

| ID | Название | Основные сервисы | Вход | Выход | Статус |
| --- | --- | --- | --- | --- | --- |
| [SETUP-01](SETUP-01-setup-wizard.md) | Мастер настройки базы знаний | Frontend Setup UI, Setup Orchestrator | Параметры проекта, файлы, решения пользователя | Опубликованная KB, статус `ready`, отчёт обработки | drafted |
| [SETUP-02](SETUP-02-document-upload.md) | Загрузка документов | Document Upload Service, Artifact Storage | Файлы из UI (`md`, `txt`, `pdf`, `docx`, `xlsx`, `csv`, `json`) | Принятые файлы в хранилище либо причина отклонения для каждого | drafted |
| [SETUP-03](SETUP-03-source-registry.md) | Реестр источников | Source Registry Service | Принятые файлы | Запись реестра на документ (checksum, статус, счётчики секций и карточек) | drafted |
| [SETUP-04](SETUP-04-document-parsing.md) | Извлечение секций | Document Parser | Исходные документы | Смысловые секции (`ParsedSection`) с результатом классификации по дереву (`classifier_result`) | drafted |
| [SETUP-12](SETUP-12-llm-taxonomy-classification.md) | Иерархическая LLM-классификация секций (3 уровня, 30-битный bitmap) — **замещена SETUP-13** | Document Parser (SVC-07; заменяет внутренний classifier) | Секция | Классы трёх уровней (30-битный bitmap), при необходимости — новые автосозданные классы | superseded by SETUP-13 |
| [SETUP-13](SETUP-13-classifier-library.md) | Библиотека классификаторов (замещает предметную модель SETUP-12) | Frontend (шаг «Классификаторы»), Document Parser | Правки дерева классов и промптов в UI; фрагмент текста при парсинге | Редактируемое дерево произвольной глубины; класс фрагмента, определённый по цепочке уровней. Целевое: metadata-хинты узлов и `resolved_hints` секции ([§8](SETUP-13-classifier-library.md#8-metadata-хинты-узлов)) | drafted |
| [SETUP-05](SETUP-05-rag-cards-generation.md) | Генерация RAG-карточек | RAG Card Generator, LLM Gateway | Классифицированные секции (`classifier_result` с хинтами) | Черновики RAG-карточек (YAML-metadata + Markdown); секции без `doc_type_hint` — явный отказ `DOC_TYPE_HINT_MISSING` | drafted |
| [SETUP-06](SETUP-06-rag-card-review.md) | Ревью RAG-карточек (HITL) | Card Review UI | Черновики карточек, решение пользователя | Карточки `approved` / `rejected` / отредактированные / на регенерацию | drafted |
| [SETUP-07](SETUP-07-metadata-validation.md) | Валидация metadata и онтологии | Metadata Validation Service | Утверждённые карточки | Отчёт валидации; пропускает в chunking только валидные карточки | drafted |
| [SETUP-08](SETUP-08-chunking.md) | Генерация чанков | Chunking Service | Валидированные карточки | Чанки с `chunk_id`, унаследованной metadata и `embedding_text` | drafted |
| [SETUP-09](SETUP-09-embeddings-index.md) | Embeddings и векторный индекс | Embedding Service, Vector DB Indexer | Чанки | Embeddings и версионированная коллекция Qdrant (`index_version`) | drafted |
| [SETUP-10](SETUP-10-retrieval-tests.md) | Retrieval smoke-тесты | RAG Evaluation Service | Новый индекс, контрольные запросы | `RetrievalEvalReport` (recall@k, precision@k, no-context rate) | drafted |
| [SETUP-11](SETUP-11-publish-kb.md) | Публикация базы знаний | Knowledge Base Registry | Зелёный retrieval-отчёт, подтверждение пользователя | Активная `kb_version`, сообщение «Knowledge Base ready» | drafted |

## Стадия 2 — Runtime (диалог ML-задачи)

| ID | Название | Основные агенты | Вход | Выход | Статус |
| --- | --- | --- | --- | --- | --- |
| [RUNTIME-01](RUNTIME-01-session.md) | Сессия + ContextMemory | `SessionAgent` | Start project; активная `kb_version` | `conversation_id`, пустая `ContextMemory` | drafted |
| [RUNTIME-02](RUNTIME-02-nlu.md) | NLU (intent + entities) | `NLUAgent` | Сообщение пользователя | `ParsedUserInput`: intent, entities, confidence, `missing_slots` | drafted |
| [RUNTIME-03](RUNTIME-03-task-discovery.md) | Task Discovery | `TaskDiscoveryAgent` | `ParsedUserInput`, ответы на уточнения | `TaskDiscoveryResult`: `task_type`, target, классы, `domain`, `data_source` | drafted |
| [RUNTIME-04](RUNTIME-04-data-profiling.md) | Data Profiling | `DataProfilingAgent` | Описание данных от пользователя (не сами данные) | `DataProfile`: объём, поля, пропуски, распределение классов, `temporal_importance` | drafted |
| [RUNTIME-05](RUNTIME-05-domain-context.md) | Domain Context | `DomainContextAgent`, `RAGRetrievalAgent` | Профиль задачи и данных, карточки KB | `DomainContext`: `critical_factors`, `interpretability_requirement`, `EvidencePack` | drafted |
| [RUNTIME-06](RUNTIME-06-feature-synthesis.md) | Feature Synthesis | `FeatureSynthesisAgent` | `ContextMemory`, `EvidencePack` | `FeatureCandidateSet`: base / derived / interaction с `evidence_doc_ids` | drafted |
| [RUNTIME-07](RUNTIME-07-feature-validation.md) | Feature Validation | `FeatureCriticAgent`, `MulticollinearityAgent` | Кандидаты признаков | `ValidationReport` по каждому признаку | drafted |
| [RUNTIME-08](RUNTIME-08-feature-review.md) | Human review признаков | Frontend Feature Approval UI | Валидированный набор, решение пользователя | `FeatureReviewDecision`, зафиксированные `final_features` | drafted |
| [RUNTIME-09](RUNTIME-09-generation-spec.md) | Эмиссия GenerationSpec | `DataGenerationSpecAgent` | `final_features`, профиль данных | `GenerationSpec` (JSON-описание, не строки данных) | drafted |
| [RUNTIME-10](RUNTIME-10-data-generation.md) | Генерация синтетических данных | DataGenerationWorker | `GenerationSpec` | `X_train.csv`, `y_train.npy`, `metadata.json`, результат валидации | drafted |
| [RUNTIME-11](RUNTIME-11-model-selection.md) | Выбор модели | `ModelSelectionAgent` | `ContextMemory`, `EvidencePack`, решение пользователя | `ModelRecommendation`, `training_config` | drafted |
| [RUNTIME-12](RUNTIME-12-export.md) | Экспорт ML-пакета | `ExportAgent` | Подтверждённая `ContextMemory` | `archive.zip` (9 файлов) + time-bound ссылка | drafted |

## Стадия 3 — Analytics

Вход фич Analytics — события Setup и Runtime (в основном только чтение). Исключения: [ANALYTICS-08](ANALYTICS-08-domain-feature-store.md) читает агрегаты feature-store из внешних источников, а [ANALYTICS-04](ANALYTICS-04-rag-content-lifecycle.md) допускает curation карточек (отправить на ревью, пометить reindex, вывести из KB).

| ID | Название | Основные сервисы | Выход | Статус |
| --- | --- | --- | --- | --- |
| [ANALYTICS-01](ANALYTICS-01-session-dashboard.md) | Дашборд воронки сессий | Analytics Service | Сессии, completion rate, drop-off по фазам, время до экспорта | drafted |
| [ANALYTICS-02](ANALYTICS-02-rag-quality.md) | Дашборд качества RAG | RAG Analytics Service | recall@k, precision@k, no-context rate, падающие запросы | drafted |
| [ANALYTICS-03](ANALYTICS-03-agent-performance.md) | Дашборд производительности агентов | Observability Service | Latency, rate repair-loop, доля валидного JSON | drafted |
| [ANALYTICS-04](ANALYTICS-04-rag-content-lifecycle.md) | Жизненный цикл RAG-контента | RAG Card Registry, Analytics Service | Устаревшие, неиспользуемые, low-confidence карточки; действия curation | drafted |
| [ANALYTICS-05](ANALYTICS-05-feature-analytics.md) | Аналитика генерации признаков | Feature Analytics Service | Rate приёмки признаков, причины отклонения | drafted |
| [ANALYTICS-06](ANALYTICS-06-dataset-quality.md) | Качество синтетических датасетов | Dataset Quality Service | Здоровье shape / NaN / баланса классов | drafted |
| [ANALYTICS-07](ANALYTICS-07-model-recommendation.md) | Аналитика рекомендаций моделей | Analytics Service | Рекомендованная vs. выбранная модель, override rate | drafted |
| [ANALYTICS-08](ANALYTICS-08-domain-feature-store.md) | Аналитика доменного feature-store | Domain Analytics Service | Агрегаты по sensor / object / environment | drafted |
| [ANALYTICS-09](ANALYTICS-09-audit-trail.md) | Сквозной audit trail | Audit Service, Traceability Service | Цепочка «исходный документ → … → экспортированный артефакт», экспорт в JSON | drafted |

## Сквозная платформа

| ID | Название | Основные сервисы | Вход → выход | Статус |
| --- | --- | --- | --- | --- |
| [PLATFORM-01](PLATFORM-01-api-backend.md) | Поверхность Backend API | FastAPI Backend, Auth Service | Запрос UI или клиента → типизированный ответ либо конверт ошибки `{ error: { code, message, details } }` | drafted |
| [PLATFORM-02](PLATFORM-02-langgraph-orchestrator.md) | LangGraph Orchestrator | LangGraph runtime | Шаг пользователя + `ContextMemory` → следующий агент / фаза, checkpoint | drafted |
| [PLATFORM-03](PLATFORM-03-structured-output-contracts.md) | Контракты структурированных выводов | Schema Registry, Pydantic Validators | Вывод LLM → валидный Pydantic-объект либо repair-промпт | drafted |
| [PLATFORM-04](PLATFORM-04-artifact-storage.md) | Artifact Storage и Download Manager | MinIO, Export Service, Download UI | Артефакты системы → conversation-scoped хранилище и time-bound ссылка скачивания | drafted |
| [PLATFORM-05](PLATFORM-05-rag-retrieval.md) | RAG Retrieval и Evidence Pack | `RAGRetrievalAgent`, RAG Retrieval Service, Evidence Pack Builder | Запрос агента (фаза, срез `ContextMemory`) → `EvidencePack` либо сигнал `need_more_context` | drafted |

## Соглашения

- Фича — это пользовательски-видимая способность (или runtime-инвариант, на который пользователь полагается), а не внутренний механизм.
- Каждая фича перечисляет FR / BR-FR, которые реализует, и тесты, которые её защищают.
- Фича «готова» только когда:
  - спецификации агентов или сервисов, от которых она зависит, существуют в [../../05-agents/](../../05-agents/) или [../../03-architecture/](../../03-architecture/),
  - контракты, от которых она зависит, существуют в [../../07-contracts/](../../07-contracts/),
  - RAG-карточки, на которые она ссылается (Setup/Runtime), существуют в [../../../rag/cards/](../../../rag/cards/) и проходят валидацию metadata,
  - тесты, перечисленные в её разделе приёмки, проходят.

## Связанные документы

- [../functional-requirements.md](../functional-requirements.md)
- [../non-functional-requirements.md](../non-functional-requirements.md)
- [../system-overview.md](../system-overview.md)
- [../../traceability/coverage-matrix.md](../../traceability/coverage-matrix.md)
- [../../03-architecture/services/README.md](../../03-architecture/services/README.md) — каталог сервисов SVC-01..SVC-38, реализующих эти фичи
