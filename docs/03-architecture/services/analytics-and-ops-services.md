# Аналитика и эксплуатация (SVC-35..SVC-38)

Сквозные сервисы. Не привязаны к конкретной стадии; обслуживают и Setup, и Runtime, и Analytics.

---

## SVC-35. Analytics Service

### Назначение

Собирает и агрегирует метрики работы системы.

### Функции

Считает показатели по setup pipeline, RAG quality, agent performance, feature generation, synthetic data quality, model recommendations и пользовательским сессиям.

### DTO

`AnalyticsEventDTO`, `AuditEventDTO`, `ValidationReportDTO`, `DatasetArtifactDTO`.

### Внешние участники

Администратор, product owner, EXT-02 RAG admin, EXT-04 ML engineer.

### Соседние сервисы

SVC-01 Frontend Analytics Dashboard, SVC-21 RAG Retrieval, SVC-19 Agent Runtime, SVC-32 Dataset Validation, SVC-06 Source Registry, SVC-15 KB Registry, SVC-36 Audit.

### Информационный обмен

С `SVC-19` — agent metrics. С `SVC-21` — retrieval logs. С `SVC-32` — data quality metrics. С `SVC-15` — KB lifecycle stats. С `SVC-01` — данные дашбордов.

### Входные данные

Events, logs, validation reports, retrieval metrics, session metrics, artifact metrics.

### Выходные данные

Дашборды, отчёты, агрегированные метрики, alerts, quality trends.

### Реализует фичи

[ANALYTICS-01..09](../../02-system/features/feature-index.md) (читающая часть).

---

## SVC-36. Audit and Traceability Service

### Назначение

Обеспечивает прослеживаемость решений от исходного документа до итогового артефакта.

### Функции

Сохраняет все важные действия: загрузка документа, генерация RAG-карточки, approval, retrieval, agent output, validation, human review, export.

### DTO

`AuditEventDTO`, `SourceDocumentDTO`, `RAGCardDTO`, `ChunkDTO`, `FeatureSpecDTO`, `ExportManifestDTO`.

### Внешние участники

Аудитор, администратор, EXT-03 SME, product owner.

### Соседние сервисы

Все ключевые: SVC-02 API Gateway, SVC-04 Setup Orchestrator, SVC-06 Source Registry, SVC-10 RAG Card Review, SVC-18 LangGraph Orchestrator, SVC-19 Agent Runtime, SVC-34 Export, SVC-35 Analytics.

### Информационный обмен

С сервисов — audit events. С `SVC-01` (Audit UI) — timeline и traceability graph. С `SVC-38` — может сохранять downloadable audit package.

### Входные данные

Audit events, before/after state, entity ids, actor id, timestamp.

### Выходные данные

Audit trail, traceability report, source-to-artifact chain, decision timeline.

### Реализует фичи

[ANALYTICS-09](../../02-system/features/ANALYTICS-09-audit-trail.md). Агент: [AuditAgent](../../05-agents/audit-agent.md).

### Принцип

Append-only. Любая «правка» — это новое событие со ссылкой на корректируемое (см. INV-Audit-001..002 в [invariants.md](../../04-domain/invariants.md)).

---

## SVC-37. Notification Service

### Назначение

Отправляет пользователю события о ходе длительных процессов.

### Функции

Уведомляет о прогрессе RAG setup, завершении индексации, ошибках, готовности Knowledge Base, завершении генерации данных и готовности export package.

### DTO

`NotificationDTO`, `AnalyticsEventDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-01 пользователь, EXT-02 RAG admin.

### Соседние сервисы

SVC-04 Setup Orchestrator, SVC-31 Synthetic Data Worker, SVC-34 Export, SVC-01 Frontend, SVC-02 API Gateway.

### Информационный обмен

С `SVC-04` — setup progress events. С `SVC-31` — generation progress events. С `SVC-34` — export ready event. С `SVC-01` — WebSocket/SSE.

### Входные данные

Workflow events, status updates, error events, user id, channel preferences.

### Выходные данные

UI notifications, progress messages, final readiness messages.

---

## SVC-38. Artifact Storage Service

### Назначение

Управляет хранением файлов, создаваемых системой.

### Функции

Сохраняет исходные документы, RAG-карточки, chunk manifests, reports, datasets, configs, generated code, archives. Выдаёт time-bound URL для скачивания.

### DTO

`SourceDocumentDTO`, `RAGCardDTO`, `DatasetArtifactDTO`, `ExportManifestDTO`.

### Внешние участники

EXT-10 Object Storage, EXT-01 пользователь при скачивании.

### Соседние сервисы

SVC-05 Document Upload, SVC-09 RAG Card Generator, SVC-11 Chunking, SVC-31 Synthetic Data Worker, SVC-34 Export, SVC-02 API Gateway, SVC-36 Audit.

### Информационный обмен

С `SVC-05` — исходные файлы. С `SVC-09` — RAG-файлы. С `SVC-31` — X/y/metadata. С `SVC-34` — итоговый archive. С `SVC-02` — download URL.

### Входные данные

Binary files, text artifacts, metadata, conversation id, artifact type.

### Выходные данные

Storage path, artifact id, download URL, file metadata.

### Реализует фичи

[PLATFORM-04](../../02-system/features/PLATFORM-04-artifact-storage.md).

### Принципы

- Conversation-scoped scoping (INV-Sec-001..002).
- TTL на download-ссылки.
- Audit на каждое скачивание.

---

## Связанные документы

- [README.md](README.md)
- [external-actors-and-systems.md](external-actors-and-systems.md)
- [../c4-container.md](../c4-container.md)
- [../../02-system/features/ANALYTICS-09-audit-trail.md](../../02-system/features/ANALYTICS-09-audit-trail.md)
- [../../11-operations/observability.md](../../11-operations/observability.md)
