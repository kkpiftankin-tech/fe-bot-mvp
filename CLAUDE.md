# CLAUDE.md

Постоянная проектная память для AI-ассистентов. Читать в первую очередь в каждой новой сессии.

## Проект

**Feature Engineering & Data Generation Multi-Agent Platform** (кодовое имя: **FE-Bot**).

Система помогает пользователю через диалог:

1. Определить ML-задачу.
2. Профилировать данные.
3. Извлечь доменный контекст через RAG.
4. Сформировать ML-признаки.
5. Сгенерировать синтетическую обучающую выборку.
6. Рекомендовать модель и training config.
7. Экспортировать воспроизводимый ML-pipeline.

Проект состоит из **трёх стадий**: **Setup** (мастер настройки базы знаний с UI), **Runtime** (мультиагентный диалог), **Analytics** (дашборды качества).

## Базовые принципы

- **Не** писать production-код до появления требований, контрактов и тестов.
- **Docs-as-code** — все решения хранятся в Markdown/YAML/JSON/Python под версионным контролем.
- **Contract-first** — каждый агент возвращает типизированную Pydantic-структуру.
- **State-first** — схема `ContextMemory` определена до узлов LangGraph.
- **RAG-first** — агенты читают из структурированной базы знаний с metadata, а не из сырых blob-ов.
- **Test-first** — у каждого агента, RAG-политики, валидатора и LangGraph-перехода есть тест.
- **Выводы LLM — это предположения; источник истины — детерминированные валидаторы.**
- Маленькие LLM (`llama3.2` через Ollama) выполняют узкие задачи; оркестрация — задача LangGraph.

## Архитектура (целевой стек)

- Python 3.12+
- FastAPI — HTTP-вход
- LangGraph — workflow / state machine
- Ollama — локальная LLM (по умолчанию `llama3.2:latest`)
- Vector DB — Qdrant
- PostgreSQL — персистентность диалогов
- MinIO — хранение артефактов
- Pydantic — схемы / контракты
- Docker Compose — локальный стек

## Жёсткие правила

- Никогда не выдумывать колонки БД, RAG-metadata или входные поля признаков.
- Каждый агентный вывод обязан соответствовать Pydantic-схеме из [schemas/](schemas/).
- Каждый признак обязан цитировать `evidence_doc_ids`.
- Каждый производный признак обязан перечислять `input_features`, которые существуют в `ContextMemory.fields` или среди ранее принятых признаков.
- Каждый временной признак требует наличия `timestamp` и `entity_id` в исходных данных.
- Сгенерированные датасеты создаются **Python-инструментами** на основе `GenerationSpec`, а не генерацией текста LLM.
- Валидаторы **не** опциональны и не подлежат обходу.

## Правила репозитория

| Тема | Местоположение |
| --- | --- |
| Бизнес-требования | [docs/01-business/](docs/01-business/) |
| Системные фичи и use cases | [docs/02-system/](docs/02-system/) |
| C4-архитектура и ADR | [docs/03-architecture/](docs/03-architecture/) |
| Доменная модель | [docs/04-domain/](docs/04-domain/) |
| Спецификации агентов | [docs/05-agents/](docs/05-agents/) |
| RAG-методология | [docs/06-rag/](docs/06-rag/) |
| Контракты структурированных выводов | [docs/07-contracts/](docs/07-contracts/) |
| Дизайн LangGraph | [docs/09-langgraph/](docs/09-langgraph/) |
| Pydantic-схемы | [schemas/](schemas/) |
| Шаблоны промптов | [prompts/](prompts/) |
| RAG-карточки | [rag/cards/](rag/cards/) |
| Реализация LangGraph | [src/fe_bot/graph/](src/fe_bot/graph/) |
| Реализация агентов | [src/fe_bot/agents/](src/fe_bot/agents/) |
| Детерминированные валидаторы | [validators/](validators/) |
| Тесты | [tests/](tests/) |
| Локальный стек | [infra/compose/](infra/compose/) |
| Legacy demo LangGraph+Ollama | [examples/demo-langgraph-reviewer/](examples/demo-langgraph-reviewer/) |

## Поток разработки

1. Обновить или создать соответствующие **docs** в `docs/`.
2. Обновить или создать **контракт** (Pydantic-схему) в `schemas/`.
3. Обновить или создать **тест** в `tests/`.
4. Реализовать код в `src/fe_bot/`.
5. Запустить валидаторы и тесты.
6. Обновить [docs/traceability/](docs/traceability/).

Полный процесс описан в [docs/00-methodology/development-process.md](docs/00-methodology/development-process.md).

## Запрещено

- Не создавать код в `src/` до появления docs и schemas.
- Не генерировать большие датасеты в ответах LLM — генерировать `GenerationSpec`, а данные пусть строят Python-инструменты.
- Не использовать один гигантский промпт на всю систему.
- Не создавать generic RAG-документы без metadata.
- Не смешивать несколько фаз в одном промпте.
- Не хранить состояние диалога в истории чата — использовать `ContextMemory`.

## Язык документации

Основной язык проекта — **русский**. Технические идентификаторы (`ContextMemory`, `FeatureSynthesisAgent`, `GenerationSpec`, имена методов и схем) остаются в латинице, поскольку привязаны к коду.

## Работа с этим репозиторием

- Прежняя маленькая demo (planner/worker/reviewer LangGraph) живёт под [examples/demo-langgraph-reviewer/](examples/demo-langgraph-reviewer/). Она сохранена как рабочий референс по локальной интеграции Ollama и **не** является создаваемой здесь системой.
- Перед написанием кода прочитать [AGENTS.md](AGENTS.md) (реестр агентов) и [docs/00-methodology/](docs/00-methodology/) (правила игры).
- Уровни отладки (локальный модуль → unit-тесты → component-тесты → локальный стек → полный Compose) описаны в [README.md](README.md).
