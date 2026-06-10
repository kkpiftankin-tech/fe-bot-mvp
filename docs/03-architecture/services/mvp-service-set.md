# Минимальный набор сервисов для MVP

Для первой версии необязательно разворачивать каждый из 38 SVC отдельным процессом. Логическое разделение остаётся, но физически сервисы группируются в 14 единиц, удобных для laptop-MVP. После MVP каждый «RAG Processing Service» и т. п. может быть выделен в самостоятельный микросервис без изменения обязанностей.

## 14 групп для MVP

| # | Группа | Включает SVC | Что обеспечивает |
| --- | --- | --- | --- |
| 1 | Frontend UI | SVC-01 | UI для всех трёх стадий |
| 2 | API Backend | SVC-02 + SVC-03 (минимальный) | HTTP-поверхность, auth-stub |
| 3 | Setup Orchestrator | SVC-04 | State machine 9 фаз Setup |
| 4 | RAG Processing Service | SVC-05 + SVC-07 + SVC-09 + SVC-11 + SVC-12 + SVC-13 | parser + card generator + chunker + embedding + indexer |
| 5 | Knowledge Base Registry | SVC-08 + SVC-14 + SVC-15 | ontology, retrieval eval, KB-версионирование |
| 6 | LangGraph Orchestrator | SVC-18 | State machine 7 runtime-фаз |
| 7 | Agent Runtime | SVC-19 + SVC-20 + SVC-23 + SVC-24 + SVC-25 + SVC-26 + SVC-27 + SVC-30 + SVC-33 | все агентные реализации + LLM Gateway |
| 8 | RAG Retrieval Service | SVC-21 + SVC-22 | retrieval + evidence pack |
| 9 | ContextMemory Service | SVC-16 + SVC-17 + SVC-29 | сессии, state, human review |
| 10 | Synthetic Data Worker | SVC-31 | производит датасеты |
| 11 | Validation Service | SVC-28 + SVC-32 | feature + dataset валидация |
| 12 | Export Service | SVC-34 | сборка archive.zip |
| 13 | Artifact Storage | SVC-38 + SVC-06 + SVC-10 | хранение файлов + source registry + card review UI-бэкенд |
| 14 | Analytics / Audit | SVC-35 + SVC-36 + SVC-37 | events, audit, notifications |

## Что это значит на практике

- В MVP всё крутится в **одном** Python-процессе `fe_bot_api` (см. [c4-container.md](../c4-container.md)). 14 групп — это разделение **внутри** процесса (по пакетам и модулям), а не отдельные контейнеры.
- Когда нагрузка вырастет, в первую очередь выделяются: `Synthetic Data Worker` (CPU-тяжёлый), `Validation Service` (CPU-тяжёлый), `RAG Processing Service` (на Setup-нагрузках). См. [deployment-view.md](../deployment-view.md).

## После MVP

Естественные точки разделения:

- `Synthetic Data Worker` → отдельный процесс (или Kubernetes Job), чтобы не блокировать API-thread.
- `Validation Service` → отдельный процесс, общий для Setup и Runtime валидаторов.
- `RAG Processing Service` → распадается на `Chunking`, `Embedding`, `Indexer` (если масштаб corpus большой).
- `Analytics Service` → отдельный read-optimized процесс (важно при росте dashboards).
- `Audit Service` → отдельный процесс с append-only WAL (важно для compliance).

## Карта «фича → группа MVP»

| Фича | Основная группа MVP |
| --- | --- |
| SETUP-01..03 | 3 Setup Orchestrator + 13 Artifact Storage |
| SETUP-04..09 | 4 RAG Processing Service |
| SETUP-07 (метаданные) | 5 Knowledge Base Registry |
| SETUP-10..11 | 5 Knowledge Base Registry |
| RUNTIME-01 | 9 ContextMemory Service |
| RUNTIME-02..06 / 09 / 11 | 7 Agent Runtime |
| RUNTIME-05 (RAG) | 8 RAG Retrieval Service |
| RUNTIME-07 | 11 Validation Service |
| RUNTIME-08 | 9 ContextMemory Service (Human Review) |
| RUNTIME-10 | 10 Synthetic Data Worker + 11 Validation Service |
| RUNTIME-12 | 12 Export Service + 13 Artifact Storage |
| ANALYTICS-01..09 | 14 Analytics / Audit |
| PLATFORM-01 | 2 API Backend |
| PLATFORM-02 | 6 LangGraph Orchestrator |
| PLATFORM-03 | 7 Agent Runtime (Pydantic-валидаторы) + 11 Validation Service |
| PLATFORM-04 | 13 Artifact Storage |

## Минимальный набор DTO для MVP

14 групп сервисов работают над сокращённым набором из 26 DTO (вместо полных 53). Минимальный набор и порядок «когда добавлять остальное» — в [data-transfer-objects.md §13](data-transfer-objects.md#13-минимальный-dto-набор-для-mvp). Соглашения по тому, **какие** хранилища поднимаются в MVP, а какие — позже, описаны в [storage-conventions.md](storage-conventions.md).

Краткая логика: в MVP всё работает поверх PostgreSQL + Qdrant + MinIO + Ollama. Redis, ClickHouse, Kafka, PostgREST подключаются на этапе post-MVP по триггерам, перечисленным в [c4-container.md](../c4-container.md#опциональные-контейнеры-post-mvp).

## Связанные документы

- [README.md](README.md)
- [data-transfer-objects.md](data-transfer-objects.md)
- [storage-conventions.md](storage-conventions.md)
- [service-interactions.md](service-interactions.md)
- [../c4-container.md](../c4-container.md)
- [../deployment-view.md](../deployment-view.md)
- [../../implementation-plan/FE-BOT-MVP.tasks.md](../../implementation-plan/FE-BOT-MVP.tasks.md)
