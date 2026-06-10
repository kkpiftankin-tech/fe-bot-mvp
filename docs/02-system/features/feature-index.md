# Индекс фич

Системные фичи, сгруппированные по стадии. ID стадий зеркалят project backlog: `SETUP-XX`, `RUNTIME-XX`, `ANALYTICS-XX`, `PLATFORM-XX`. У каждой фичи свой файл в этом каталоге со ссылками на требования, агентов, контракты, RAG-документы и критерии приёмки.

## Стадия 1 — Setup (мастер базы знаний)

| ID | Название | Основные сервисы | Статус |
| --- | --- | --- | --- |
| [SETUP-01](SETUP-01-setup-wizard.md) | Мастер настройки базы знаний | Frontend Setup UI, Setup Orchestrator | drafted |
| [SETUP-02](SETUP-02-document-upload.md) | Загрузка документов | Document Upload Service, Artifact Storage | drafted |
| [SETUP-03](SETUP-03-source-registry.md) | Реестр источников | Source Registry Service | drafted |
| [SETUP-04](SETUP-04-document-parsing.md) | Извлечение секций | Document Parser | drafted |
| [SETUP-05](SETUP-05-rag-card-generation.md) | Генерация RAG-карточек | RAG Card Generator, LLM Gateway | drafted |
| [SETUP-06](SETUP-06-rag-card-review.md) | Ревью RAG-карточек (HITL) | Card Review UI | drafted |
| [SETUP-07](SETUP-07-metadata-validation.md) | Валидация metadata и онтологии | Metadata Validation Service | drafted |
| [SETUP-08](SETUP-08-chunking.md) | Генерация чанков | Chunking Service | drafted |
| [SETUP-09](SETUP-09-embeddings-index.md) | Embeddings и векторный индекс | Embedding Service, Vector DB Indexer | drafted |
| [SETUP-10](SETUP-10-retrieval-tests.md) | Retrieval smoke-тесты | RAG Evaluation Service | drafted |
| [SETUP-11](SETUP-11-publish-kb.md) | Публикация базы знаний | Knowledge Base Registry | drafted |

## Стадия 2 — Runtime (диалог ML-задачи)

| ID | Название | Основные агенты | Статус |
| --- | --- | --- | --- |
| [RUNTIME-01](RUNTIME-01-session.md) | Сессия + ContextMemory | `SessionAgent` | drafted |
| [RUNTIME-02](RUNTIME-02-nlu.md) | NLU (intent + entities) | `NLUAgent` | drafted |
| [RUNTIME-03](RUNTIME-03-task-discovery.md) | Task Discovery | `TaskDiscoveryAgent` | drafted |
| [RUNTIME-04](RUNTIME-04-data-profiling.md) | Data Profiling | `DataProfilingAgent` | drafted |
| [RUNTIME-05](RUNTIME-05-domain-context.md) | Domain Context | `DomainContextAgent`, `RAGRetrievalAgent` | drafted |
| [RUNTIME-06](RUNTIME-06-feature-synthesis.md) | Feature Synthesis | `FeatureSynthesisAgent` | drafted |
| [RUNTIME-07](RUNTIME-07-feature-validation.md) | Feature Validation | `FeatureCriticAgent`, `MulticollinearityAgent` | drafted |
| [RUNTIME-08](RUNTIME-08-feature-review.md) | Human review признаков | Frontend Feature Approval UI | drafted |
| [RUNTIME-09](RUNTIME-09-generation-spec.md) | Эмиссия GenerationSpec | `DataGenerationSpecAgent` | drafted |
| [RUNTIME-10](RUNTIME-10-data-generation.md) | Генерация синтетических данных | DataGenerationWorker | drafted |
| [RUNTIME-11](RUNTIME-11-model-selection.md) | Выбор модели | `ModelSelectionAgent` | drafted |
| [RUNTIME-12](RUNTIME-12-export.md) | Экспорт ML-пакета | `ExportAgent` | drafted |

## Стадия 3 — Analytics

| ID | Название | Основные сервисы | Статус |
| --- | --- | --- | --- |
| [ANALYTICS-01](ANALYTICS-01-session-dashboard.md) | Дашборд воронки сессий | Analytics Service | drafted |
| [ANALYTICS-02](ANALYTICS-02-rag-quality.md) | Дашборд качества RAG | RAG Analytics Service | drafted |
| [ANALYTICS-03](ANALYTICS-03-agent-performance.md) | Дашборд производительности агентов | Observability Service | drafted |
| [ANALYTICS-04](ANALYTICS-04-rag-content-lifecycle.md) | Жизненный цикл RAG-контента | RAG Card Registry, Analytics Service | drafted |
| [ANALYTICS-05](ANALYTICS-05-feature-analytics.md) | Аналитика генерации признаков | Feature Analytics Service | drafted |
| [ANALYTICS-06](ANALYTICS-06-dataset-quality.md) | Качество синтетических датасетов | Dataset Quality Service | drafted |
| [ANALYTICS-07](ANALYTICS-07-model-recommendation.md) | Аналитика рекомендаций моделей | Analytics Service | drafted |
| [ANALYTICS-08](ANALYTICS-08-domain-feature-store.md) | Аналитика доменного feature-store | Domain Analytics Service | drafted |
| [ANALYTICS-09](ANALYTICS-09-audit-trail.md) | Сквозной audit trail | Audit Service, Traceability Service | drafted |

## Сквозная платформа

| ID | Название | Основные сервисы | Статус |
| --- | --- | --- | --- |
| [PLATFORM-01](PLATFORM-01-api-backend.md) | Поверхность Backend API | FastAPI Backend, Auth Service | drafted |
| [PLATFORM-02](PLATFORM-02-langgraph-orchestrator.md) | LangGraph Orchestrator | LangGraph runtime | drafted |
| [PLATFORM-03](PLATFORM-03-structured-output-contracts.md) | Контракты структурированных выводов | Schema Registry, Pydantic Validators | drafted |
| [PLATFORM-04](PLATFORM-04-artifact-storage.md) | Artifact Storage и Download Manager | MinIO, Export Service, Download UI | drafted |

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
