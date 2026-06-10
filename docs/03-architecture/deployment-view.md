# Вид развёртывания

## Цель

Показать, как контейнеры из [c4-container.md](c4-container.md) разворачиваются в локальной (default), staging и опциональной cloud-конфигурации.

## Локальная разработка (по умолчанию)

Полный стек на ноутбуке через Docker Compose. Профили в [infra/compose/docker-compose.yml](../../infra/compose/docker-compose.yml).

```text
┌─────────────────────────────── localhost ───────────────────────────────┐
│                                                                         │
│  ┌─ profile: infra ──────────┐  ┌─ profile: llm ──────────┐             │
│  │  postgres:16              │  │  ollama (llama3.2)      │             │
│  │  qdrant                   │  │  port 11434              │            │
│  │  minio (port 9000/9001)   │  └──────────────────────────┘            │
│  └───────────────────────────┘                                          │
│                                                                         │
│  ┌─ profile: app ────────────────────────────────────────────┐          │
│  │  fe_bot_api (FastAPI + Setup Orch + LangGraph + Agent     │          │
│  │  Runtime + RAG Service + LLM Gateway + Data Gen Worker    │          │
│  │  + Validation Worker + Export Service + Analytics + Audit)│          │
│  │  port 8000                                                │          │
│  └────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
```

`make up-infra` — поднимает только хранилища + Ollama. `make up-all` — добавляет приложение.

В MVP всё приложение крутится в **одном** контейнере `fe_bot_api`. Логическое разделение на компоненты — внутри процесса (один Python). Это сознательный выбор для laptop-scale.

## Staging / Production (опционально)

При горизонтальном масштабировании каждый контейнер можно выделить отдельно. Минимальное разделение:

| Узел | Контейнеры | Заметки |
| --- | --- | --- |
| `app` | API Backend + Setup Orch + LangGraph Orch + Agent Runtime + RAG Service + LLM Gateway + Export Service + Analytics + Audit | Stateless; горизонтально масштабируется |
| `worker` | Data Generation Worker + Validation Worker | Long-running; вынести из request-path |
| `data-postgres` | PostgreSQL | StatefulSet, бэкапы |
| `data-qdrant` | Qdrant | StatefulSet |
| `data-minio` | MinIO (или managed S3) | Conversation-scoped buckets |
| `llm` | Ollama (или managed inference) | Может быть GPU-нодой |
| `data-redis` *(опц.)* | Redis 7 | Shared cache, прогресс jobs, Pub/Sub. Подключается, когда `app` масштабируется горизонтально |
| `data-clickhouse` *(опц.)* | ClickHouse 24+ | Аналитика и audit timeline. Подключается, когда нагрузка на PostgreSQL events растёт |
| `bus-kafka` *(опц.)* | Kafka / Redpanda | Поток событий audit/analytics/notifications. Подключается с выделением workers |
| `postgrest` *(опц.)* | PostgREST 12+ | Read-only REST-фасад над PostgreSQL для админских UI |

Балансировщик: nginx / Traefik перед `app`. TLS — managed.

## Зависимости при старте

```text
postgres ──┐
qdrant ────┼──► fe_bot_api (api_backend)
minio ─────┤
ollama ────┘
```

`fe_bot_api` ждёт healthcheck-ов хранилищ и Ollama (retry с backoff). При недоступности любого — `/health` возвращает деградацию + код причины.

## Сетевые границы

- `localhost` (development): всё на петле; UI ходит на `127.0.0.1:8000`.
- staging / prod: `app` доступен снаружи через ingress; хранилища и Ollama — только внутри VPC/network.

## Объёмы данных (эталон)

| Компонент | Размер |
| --- | --- |
| Qdrant index (10k chunks, 384d, FP16) | ≈ 50–80 MB |
| MinIO per-conversation (X+y+archive) | ≈ 100–200 MB (за 100k×19) |
| PostgreSQL conversations (1k активных) | ≈ 200–500 MB |
| Ollama model (llama3.2 4-bit) | ≈ 2 GB |

## Связанные документы

- [c4-container.md](c4-container.md)
- [services/storage-conventions.md](services/storage-conventions.md) — какой DTO на каком слое и когда подключается опциональное хранилище
- [services/data-transfer-objects.md](services/data-transfer-objects.md)
- [adr/ADR-001-langgraph-as-orchestrator.md](adr/ADR-001-langgraph-as-orchestrator.md)
- [adr/ADR-002-ollama-default-llm.md](adr/ADR-002-ollama-default-llm.md)
- [adr/ADR-003-qdrant-as-vector-db.md](adr/ADR-003-qdrant-as-vector-db.md)
- [../11-operations/deployment.md](../11-operations/deployment.md)
