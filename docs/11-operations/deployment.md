# Развёртывание

## Локальная разработка

```bash
make install-dev
make up-infra       # postgres + qdrant + minio
make up-llm         # ollama (если не установлен нативно)
make run-api-reload # FastAPI hot-reload
```

Или одной строкой:

```bash
make up-all         # infra + llm + app
```

## Compose-профили

| Профиль | Сервисы |
| --- | --- |
| `infra` | postgres, qdrant, minio |
| `llm` | ollama |
| `app` | fe_bot_api |

## Переменные окружения

| Переменная | Дефолт | Назначение |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://fe_bot:fe_bot@postgres:5432/fe_bot` | Postgres |
| `VECTOR_DB_URL` | `http://qdrant:6333` | Qdrant |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama |
| `ARTIFACT_STORE_ENDPOINT` | `http://minio:9000` | MinIO endpoint |
| `ARTIFACT_STORE_ACCESS_KEY` | `minioadmin` | MinIO key |
| `ARTIFACT_STORE_SECRET_KEY` | `minioadmin` | MinIO secret |
| `LLM_MODEL` | `llama3.2:latest` | Модель Ollama |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding-модель |
| `LOG_LEVEL` | `INFO` | Уровень логов |

## Healthchecks

| Эндпоинт | Что проверяет |
| --- | --- |
| `GET /health` | live + connectivity Postgres / Qdrant / Ollama / MinIO |
| `GET /metrics` | Prometheus exposition |

## Откат

- Опубликованная `kb_version` иммутабельна. Откат — переключение указателя `active` на предыдущую `kb_version`.
- Образ приложения версионируется по git-tag; deploy = `docker pull && docker compose up -d --no-deps fe_bot_api`.

## Связанные документы

- [../03-architecture/deployment-view.md](../03-architecture/deployment-view.md)
- [observability.md](observability.md)
- [metrics.md](metrics.md)
- [runbook.md](runbook.md)
