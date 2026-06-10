# Соглашения по хранилищам

Документ описывает физические хранилища, на которые ссылается [data-transfer-objects.md](data-transfer-objects.md). Каждый DTO в каталоге явно указывает основное хранилище и опциональные дополнительные. Здесь зафиксирован смысл каждого хранилища и в каком наборе они появляются на разных этапах развития системы.

## Слои хранения

| Хранилище | Назначение | Конкретная технология (default) |
| --- | --- | --- |
| **PostgreSQL** | Основное транзакционное хранилище: сессии, документы, карточки, версии, статусы, ContextMemory | PostgreSQL 16 |
| **PostgREST** | Опциональный REST-фасад над PostgreSQL для административных UI/API | PostgREST 12+ |
| **Redis** | Быстрый cache, transient state, прогресс long-running jobs, locks, Pub/Sub для UI | Redis 7 |
| **ClickHouse** | Аналитические события, метрики агентов, RAG quality, latency, dashboard data | ClickHouse 24+ |
| **Kafka** | Потоковые события: progress, audit, analytics, notifications | Apache Kafka 3.x / Redpanda |
| **Vector DB** | Embeddings, chunk vectors, retrieval metadata | Qdrant (см. ADR-003) |
| **Object Storage** | Файлы: исходные документы, RAG-card markdown, CSV/NPY/YAML/Python/ZIP | MinIO (S3-совместимое) |
| **Не хранится** | DTO транзитен (request/response внутри процесса) | — |

## Назначение по типам данных

| Тип данных | Где жить | Почему |
| --- | --- | --- |
| Состояние сессии (ContextMemory, Setup job) | PostgreSQL + Redis cache | Транзакционно + быстрый доступ |
| История диалога | PostgreSQL | Транзакционно, нужен для аудита и восстановления |
| Embeddings, retrieval | Vector DB + metadata в PostgreSQL | Векторный поиск отдельная задача |
| Файлы (docs, datasets, archives) | Object Storage + metadata в PostgreSQL | Большие бинарники не для SQL |
| Аналитические события | ClickHouse | Колоночное хранилище, агрегаты, long-tail метрики |
| Поток событий между сервисами | Kafka | Decoupling producer↔consumer, retention |
| Прогресс long-running jobs, agent cache | Redis | Низкая задержка, TTL |
| Аудит-трейл | ClickHouse (timeline) + PostgreSQL (критичные) | Аналитика и compliance одновременно |
| Уведомления UI | Redis + Kafka/WebSocket/SSE | Низкая задержка + поток |

## Эволюция стека

### MVP (laptop, single-process)

Минимальный набор:

| Слой | Технология | Notes |
| --- | --- | --- |
| PostgreSQL | PostgreSQL 16 | Сессии, документы, карточки, ContextMemory, аудит (single-table) |
| Vector DB | Qdrant | Setup и Runtime retrieval |
| Object Storage | MinIO | Conversation-scoped buckets |
| LLM | Ollama (`llama3.2`) | Inference + опционально embeddings |

Что **не** разворачивается в MVP:

- **Redis** — заменяется in-process LRU-cache и PostgreSQL.
- **ClickHouse** — аналитика лежит в PostgreSQL (events-таблица); метрики читаются прямыми SQL-запросами.
- **Kafka** — события публикуются внутрипроцессно (Python pubsub) или через PostgreSQL LISTEN/NOTIFY.
- **PostgREST** — административные эндпоинты пишутся вручную в FastAPI.

Это компромисс laptop-MVP. См. [mvp-service-set.md](mvp-service-set.md) и [../deployment-view.md](../deployment-view.md).

### Post-MVP (staging / production)

По мере роста выделяются:

1. **Redis** — когда in-process cache перестаёт хватать (несколько реплик `app`, нужен shared cache).
2. **ClickHouse** — когда аналитика начинает тормозить PostgreSQL или требуются dashboards с большой глубиной (audit, RAG quality, model recommendations).
3. **Kafka** — когда появляются независимые workers, требующие надёжной доставки событий (synthetic data worker, validation worker, audit pipeline).
4. **PostgREST** — когда нужен административный read-only API над PostgreSQL без написания endpoints.

Порядок выделения зависит от boundlene-метрик; типично: ClickHouse → Redis → Kafka → PostgREST.

## Правила выбора хранилища при добавлении DTO

1. **DTO транзитен (только request/response в рамках одного вызова)** → не хранить; логировать в ClickHouse при необходимости.
2. **DTO — это сущность с lifecycle (создание, обновление, статусы)** → PostgreSQL основное; добавить Redis-cache, если читается на каждый шаг.
3. **DTO содержит крупный текст/бинарь** → Object Storage; metadata в PostgreSQL.
4. **DTO — это аналитическое событие** → ClickHouse основное; Kafka для потока; PostgreSQL дубль для критичного аудита.
5. **DTO — это embedding/чанк** → Vector DB основное; metadata в PostgreSQL.
6. **DTO — это пользовательское уведомление** → Redis (short TTL) + Kafka/WebSocket для доставки; PostgreSQL опционально для истории.

## Связанные документы

- [data-transfer-objects.md](data-transfer-objects.md)
- [README.md](README.md)
- [mvp-service-set.md](mvp-service-set.md)
- [../c4-container.md](../c4-container.md)
- [../deployment-view.md](../deployment-view.md)
- [../adr/ADR-003-qdrant-as-vector-db.md](../adr/ADR-003-qdrant-as-vector-db.md)
