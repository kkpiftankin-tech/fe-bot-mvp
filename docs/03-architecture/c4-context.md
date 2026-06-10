# C4 — Уровень 1: Context

## Назначение

Показать систему FE-Bot как единый чёрный ящик, окружённый внешними акторами и системами, с которыми она обменивается данными.

## Диаграмма (Mermaid)

```mermaid
C4Context
  title FE-Bot — System Context

  Person(ml_engineer, "ML-инженер / Data Scientist", "Ведёт диалог, ревьюит признаки, получает экспорт-пакет")
  Person(rag_admin, "RAG Knowledge Base Admin", "Загружает доменные документы, ревьюит карточки")
  Person(product_owner, "Product Owner / Architect", "Читает Analytics-дашборды и audit trail")
  Person(domain_sme, "Доменный SME", "Опционально: ревьюит карточки и признаки")

  System(fe_bot, "FE-Bot", "Мультиагентная платформа Setup + Runtime + Analytics. Превращает доменные документы и описание задачи в воспроизводимый ML-пакет")

  System_Ext(ollama, "Ollama LLM Runtime", "Локальный inference small-LLM (по умолчанию llama3.2:latest)")
  System_Ext(embedding_model, "Embedding Service", "Sentence-transformer, 384 dims")
  System_Ext(qdrant, "Qdrant Vector DB", "Поиск по embeddings + metadata-фильтры")
  System_Ext(postgres, "PostgreSQL", "Сессии, ContextMemory, audit log")
  System_Ext(minio, "MinIO Artifact Storage", "X_train.csv, archive.zip и др.")
  System_Ext(observability, "Observability (Prometheus / OpenTelemetry)", "Metrics + tracing")

  Rel(ml_engineer, fe_bot, "Использует Runtime-чат и Download Manager", "HTTPS")
  Rel(rag_admin, fe_bot, "Использует Setup-мастер", "HTTPS")
  Rel(product_owner, fe_bot, "Использует Analytics-дашборды", "HTTPS")
  Rel(domain_sme, fe_bot, "Ревьюит карточки и признаки", "HTTPS")

  Rel(fe_bot, ollama, "LLM-инференс", "HTTP")
  Rel(fe_bot, embedding_model, "Получение embeddings", "in-process / HTTP")
  Rel(fe_bot, qdrant, "Vector search + индексация", "gRPC / HTTP")
  Rel(fe_bot, postgres, "Read/write сессий и audit", "PostgreSQL wire")
  Rel(fe_bot, minio, "Read/write артефактов", "S3 API")
  Rel(fe_bot, observability, "Метрики, логи, трейсы", "OTLP / Prometheus scrape")
```

## Внешние акторы и системы

- **ML-инженер / Data Scientist** — основной runtime-пользователь. Видит чат-UI, прогресс по 7 фазам, обзор признаков и Download Manager.
- **RAG Knowledge Base Admin** — основной setup-пользователь. Видит мастер из 9 фаз, реестр источников, ревью карточек.
- **Product Owner / Architect** — основной analytics-пользователь. Видит дашборды качества, audit trail.
- **Доменный SME** — опциональный участник на ревью карточек ([SETUP-06](../02-system/features/SETUP-06-rag-card-review.md)) и/или подтверждении признаков ([RUNTIME-08](../02-system/features/RUNTIME-08-feature-review.md)).
- **Ollama** — внешний процесс с локальной LLM. Любой вызов LLM из FE-Bot идёт через `LLM Gateway`.
- **Embedding Service** — модель sentence-transformer, размерность 384. Может быть встроена в процесс или вынесена в отдельный сервис.
- **Qdrant** — векторная БД. Хранит embedded-chunks с metadata. Поддерживает фильтры по `doc_type`, `domain`, `task_type`, `data_source`, `phase`.
- **PostgreSQL** — сессии, ContextMemory snapshots, audit log, source registry, RAG card registry, knowledge base registry, event log.
- **MinIO** — объектное хранилище. Conversation-scoped префиксы. Time-bound presigned URLs.
- **Observability** — Prometheus + OpenTelemetry (опционально). Метрики из [docs/11-operations/metrics.md](../11-operations/metrics.md).

## Что НЕ показано здесь

- Внутренние компоненты FE-Bot (см. [c4-container.md](c4-container.md)).
- Реальный поток данных по фазам (см. [c4-component-agent-runtime.md](c4-component-agent-runtime.md), [c4-component-rag-service.md](c4-component-rag-service.md), [c4-component-setup-orchestrator.md](c4-component-setup-orchestrator.md)).
- Развёртывание (см. [deployment-view.md](deployment-view.md)).

## Связанные документы

- [c4-container.md](c4-container.md)
- [deployment-view.md](deployment-view.md)
- [../02-system/system-overview.md](../02-system/system-overview.md)
- [../02-system/actors.md](../02-system/actors.md)
