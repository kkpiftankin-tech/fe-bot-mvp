# Внешние участники и системы

Каталог внешних участников (`EXT-XX`), на которые ссылаются сервисы. Это либо люди в определённых ролях, либо внешние программные системы.

## Люди

### EXT-01. Пользователь / аналитик

Загружает документы, запускает настройку RAG, описывает ML-задачу, подтверждает признаки, выбирает модель и скачивает артефакты.

См. также: [docs/01-business/stakeholders.md](../../01-business/stakeholders.md), [docs/02-system/actors.md](../../02-system/actors.md).

### EXT-02. Администратор RAG

Отвечает за качество базы знаний: проверяет RAG-карточки, исправляет metadata, запускает reindex, анализирует retrieval-ошибки.

### EXT-03. Предметный SME

Проверяет доменные признаки, корректность формул, смысл RAG-карточек и релевантность критичных факторов.

### EXT-04. Data Scientist / ML Engineer

Использует результат системы: `features.json`, `GenerationSpec`, обучающую выборку, `training_config`, `pipeline.py`.

### EXT-05. DevOps / MLOps-инженер

Разворачивает сервисы, настраивает хранилища, observability, доступы, окружения и deployment.

## Внешние системы

### EXT-06. Identity Provider

Внешняя система аутентификации и авторизации.

### EXT-07. Ollama / локальная LLM

Локальный runtime малой LLM, например `llama3.2`, используемый агентами для структурированных узких задач. См. [ADR-002](../adr/ADR-002-ollama-default-llm.md).

### EXT-08. Embedding Model

Модель для построения embeddings по RAG-чанкам. По умолчанию — 384-мерный sentence-transformer (см. NFR-Perf-002).

### EXT-09. Vector DB

Векторная БД: Qdrant в MVP. См. [ADR-003](../adr/ADR-003-qdrant-as-vector-db.md).

### EXT-10. Object Storage

Хранилище файлов: MinIO в локальной разработке, S3-совместимое в облачном варианте.

### EXT-11. Feature Store

Хранилище формализованных аналитических признаков и feature tables. Питает [ANALYTICS-08](../../02-system/features/ANALYTICS-08-domain-feature-store.md) и доменные analytics-карточки.

### EXT-12. Model Registry

Хранилище моделей, training configs и версий ML-артефактов (опциональный компонент пост-MVP).

### EXT-13. Data Sources

Внешние источники данных: CSV, SQL, формулы фактической обстановки, `tracks_fused`, `external_conditions`, sensor logs, AIS, radar, sonar, ESM. Питают batch-агрегации feature-store.

## Карта взаимодействий

| EXT | Через кого попадает в систему |
| --- | --- |
| EXT-01..EXT-05 | UI → API Gateway (SVC-01, SVC-02) |
| EXT-06 | Auth Service (SVC-03) |
| EXT-07 | LLM Gateway (SVC-20) |
| EXT-08 | Embedding Service (SVC-12) |
| EXT-09 | Vector Indexer (SVC-13), RAG Retrieval (SVC-21) |
| EXT-10 | Artifact Storage Service (SVC-38) |
| EXT-11 | Domain Analytics Service / Feature Store (опц.) |
| EXT-12 | Export Service (опц.) |
| EXT-13 | Batch Aggregation Worker (опц.) |

## Связанные документы

- [README.md](README.md)
- [../c4-context.md](../c4-context.md)
- [../../02-system/actors.md](../../02-system/actors.md)
- [../../01-business/stakeholders.md](../../01-business/stakeholders.md)
