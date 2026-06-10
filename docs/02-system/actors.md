# Акторы

Кто или что взаимодействует с FE-Bot на runtime. Отличается от [01-business/stakeholders.md](../01-business/stakeholders.md), где перечислены люди, *управляющие* проектом. Здесь — те, кто *использует* работающую систему.

## Основной актор

### A-01. ML-инженер (конечный пользователь)

- Ведёт диалог через восемь фаз.
- Даёт текстовые описания задачи, опциональные подсказки по полям, опциональные подсказки по классам.
- Ревьюит и подтверждает `final_features` до перехода к data generation.
- Ревьюит и подтверждает `recommended_model` до экспорта.

## Вторичные акторы

### A-02. Доменный SME

- Опционально. Привлекается асинхронно через будущую поверхность human-review.
- В MVP роль SME играет ML-инженер.

### A-03. Администратор базы знаний RAG

- Не runtime-актор внутри диалога.
- Управляет ingestion-pipeline (сырые docs → карточки → чанки → индекс).
- Документировано в [../06-rag/ingestion-pipeline.md](../06-rag/ingestion-pipeline.md).

## Системные акторы

### A-04. Сервис Ollama LLM

- Внешний процесс, предоставляющий локальный LLM-inference. Модель по умолчанию: `llama3.2:latest`.
- Вызывается каждым агентом, делающим понимание или генерацию языка.

### A-05. Qdrant Vector DB

- Внешний процесс, хранящий embedded-чанки RAG.
- Запрашивается `RAGRetriever`-ом с metadata-фильтрами.

### A-06. PostgreSQL

- Хранит сериализованную `ContextMemory` по `conversation_id`.
- Используется слоем checkpoint/persistence LangGraph.

### A-07. Artifact Storage (MinIO)

- Хранит `archive.zip`, `X_train.csv`, `y_train.npy`, `pipeline.py`, `metadata.json`.
- Scoped по `conversation_id`.

### A-08. DataGenerationWorker

- Внутренний Python-worker. Не LLM-агент.
- Потребляет `GenerationSpec`, эмитит датасет и `ValidationReport`.

### A-09. ValidationWorker

- Внутренний Python-worker. Запускает детерминированные валидаторы на агентных выводах и сгенерированных данных.

## Матрица акторов по фазам

| Фаза | Основной актор | Системные акторы |
| --- | --- | --- |
| `initialization` | ML-инженер | PostgreSQL |
| `task_discovery` | ML-инженер | Ollama |
| `data_profiling` | ML-инженер | Ollama, Qdrant |
| `domain_context` | ML-инженер | Ollama, Qdrant |
| `feature_synthesis` | ML-инженер | Ollama, Qdrant, ValidationWorker |
| `data_generation` | (авто, гейтится подтверждением пользователя) | DataGenerationWorker, ValidationWorker, MinIO |
| `model_selection` | ML-инженер | Ollama, Qdrant |
| `export` | (авто) | MinIO |

## Границы доверия

| Граница | Внутри | Снаружи |
| --- | --- | --- |
| Граница пользовательского ввода | Валидация запроса FastAPI | Свободный текст пользователя |
| Граница LLM | Pydantic-валидированные структурированные выводы | Строки-ответы Ollama |
| Граница RAG | EvidencePack (компактный, agent-scoped) | Сырое содержимое карточек |
| Граница хранилища | Conversation-scoped префикс MinIO | Артефакты других диалогов |

Пересечение границы требует валидатора. См. [../00-methodology/development-process.md](../00-methodology/development-process.md) и [../03-architecture/c4-container.md](../03-architecture/c4-container.md).

## Связанные документы

- [system-overview.md](system-overview.md)
- [../01-business/stakeholders.md](../01-business/stakeholders.md)
- [../03-architecture/c4-context.md](../03-architecture/c4-context.md)
