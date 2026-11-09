# Feature → SVC (карта)

Связывает фичи из [docs/02-system/features/](../02-system/features/) с конкретными сервисами из [docs/03-architecture/services/](../03-architecture/services/). Используется для ответа на вопрос «какие сервисы нужно тронуть, чтобы реализовать фичу X».

## Setup

| Фича | Основные SVC |
| --- | --- |
| [SETUP-01 Мастер настройки](../02-system/features/SETUP-01-setup-wizard.md) | SVC-01, SVC-02, SVC-04, SVC-37 |
| [SETUP-02 Загрузка документов](../02-system/features/SETUP-02-document-upload.md) | SVC-05, SVC-38, SVC-06 |
| [SETUP-03 Реестр источников](../02-system/features/SETUP-03-source-registry.md) | SVC-06, SVC-36 |
| [SETUP-04 Извлечение секций](../02-system/features/SETUP-04-document-parsing.md) | SVC-07, SVC-06 |
| [SETUP-05 Генерация RAG-карточек](../02-system/features/SETUP-05-rag-cards-generation.md) | SVC-09, SVC-20, SVC-08; целевое: `ClassificationMetadataResolver` внутри SVC-09 читает хинты дерева SETUP-13 ([ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)) |
| [SETUP-06 Ревью карточек](../02-system/features/SETUP-06-rag-card-review.md) | SVC-10, SVC-01, SVC-36 |
| [SETUP-07 Валидация metadata](../02-system/features/SETUP-07-metadata-validation.md) | SVC-08 |
| [SETUP-08 Чанкование](../02-system/features/SETUP-08-chunking.md) | SVC-11 |
| [SETUP-09 Embeddings и индекс](../02-system/features/SETUP-09-embeddings-index.md) | SVC-12, SVC-13 |
| [SETUP-10 Retrieval-тесты](../02-system/features/SETUP-10-retrieval-tests.md) | SVC-14, SVC-21 |
| [SETUP-11 Публикация KB](../02-system/features/SETUP-11-publish-kb.md) | SVC-15, SVC-37, SVC-36 |
| [SETUP-12 Иерархическая LLM-классификация секций](../02-system/features/SETUP-12-llm-taxonomy-classification.md) (замещена SETUP-13) | SVC-07, SVC-09, SVC-25, SVC-12, SVC-36 |
| [SETUP-13 Библиотека классификаторов](../02-system/features/SETUP-13-classifier-library.md) | SVC-07 (подключение к парсеру), SVC-01 (шаг мастера); отдельный SVC не выделен |

## Runtime

| Фича | Основные SVC |
| --- | --- |
| [RUNTIME-01 Сессия](../02-system/features/RUNTIME-01-session.md) | SVC-16, SVC-17 |
| [RUNTIME-02 NLU](../02-system/features/RUNTIME-02-nlu.md) | SVC-23, SVC-21 |
| [RUNTIME-03 Task Discovery](../02-system/features/RUNTIME-03-task-discovery.md) | SVC-24, SVC-21 |
| [RUNTIME-04 Data Profiling](../02-system/features/RUNTIME-04-data-profiling.md) | SVC-25, SVC-21, SVC-28 |
| [RUNTIME-05 Domain Context](../02-system/features/RUNTIME-05-domain-context.md) | SVC-26, SVC-21 |
| [RUNTIME-06 Feature Synthesis](../02-system/features/RUNTIME-06-feature-synthesis.md) | SVC-27, SVC-21 |
| [RUNTIME-07 Feature Validation](../02-system/features/RUNTIME-07-feature-validation.md) | SVC-28 |
| [RUNTIME-08 Human review признаков](../02-system/features/RUNTIME-08-feature-review.md) | SVC-29, SVC-01 |
| [RUNTIME-09 GenerationSpec](../02-system/features/RUNTIME-09-generation-spec.md) | SVC-30, SVC-28 |
| [RUNTIME-10 Synthetic Data](../02-system/features/RUNTIME-10-data-generation.md) | SVC-31, SVC-32 |
| [RUNTIME-11 Model Selection](../02-system/features/RUNTIME-11-model-selection.md) | SVC-33 |
| [RUNTIME-12 Export](../02-system/features/RUNTIME-12-export.md) | SVC-34, SVC-38 |

## Analytics

| Фича | Основные SVC |
| --- | --- |
| [ANALYTICS-01 Воронка сессий](../02-system/features/ANALYTICS-01-session-dashboard.md) | SVC-35 |
| [ANALYTICS-02 Качество RAG](../02-system/features/ANALYTICS-02-rag-quality.md) | SVC-35, SVC-21 |
| [ANALYTICS-03 Performance агентов](../02-system/features/ANALYTICS-03-agent-performance.md) | SVC-35, SVC-19 |
| [ANALYTICS-04 RAG lifecycle](../02-system/features/ANALYTICS-04-rag-content-lifecycle.md) | SVC-35, SVC-15 |
| [ANALYTICS-05 Feature analytics](../02-system/features/ANALYTICS-05-feature-analytics.md) | SVC-35, SVC-27, SVC-28 |
| [ANALYTICS-06 Dataset quality](../02-system/features/ANALYTICS-06-dataset-quality.md) | SVC-35, SVC-32 |
| [ANALYTICS-07 Model recommendation](../02-system/features/ANALYTICS-07-model-recommendation.md) | SVC-35, SVC-33 |
| [ANALYTICS-08 Domain feature store](../02-system/features/ANALYTICS-08-domain-feature-store.md) | SVC-35 + EXT-11 Feature Store |
| [ANALYTICS-09 Audit trail](../02-system/features/ANALYTICS-09-audit-trail.md) | SVC-36 |

## Platform

| Фича | Основные SVC |
| --- | --- |
| [PLATFORM-01 API Backend](../02-system/features/PLATFORM-01-api-backend.md) | SVC-02, SVC-03 |
| [PLATFORM-02 LangGraph Orchestrator](../02-system/features/PLATFORM-02-langgraph-orchestrator.md) | SVC-18 |
| [PLATFORM-03 Structured contracts](../02-system/features/PLATFORM-03-structured-output-contracts.md) | SVC-19, SVC-20, SVC-28 |
| [PLATFORM-04 Artifact Storage](../02-system/features/PLATFORM-04-artifact-storage.md) | SVC-38 |
| [PLATFORM-05 RAG Retrieval и Evidence Pack](../02-system/features/PLATFORM-05-rag-retrieval.md) | SVC-21, SVC-22, SVC-15 |

## Правила

- При добавлении новой фичи — добавить строку сюда.
- При добавлении нового SVC — пройтись по фичам, которые на него опираются.
- Висячая ссылка на отсутствующий SVC или фичу — это баг.

## Связанные документы

- [coverage-matrix.md](coverage-matrix.md)
- [agent-to-contract-map.md](agent-to-contract-map.md)
- [../02-system/features/feature-index.md](../02-system/features/feature-index.md)
- [../03-architecture/services/README.md](../03-architecture/services/README.md)
