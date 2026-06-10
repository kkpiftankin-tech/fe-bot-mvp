# FE-Bot — мультиагентная платформа Feature Engineering & Data Generation

Docs-as-code, contract-first мультиагентная система, которая превращает разговорный ML-бриф в воспроизводимый экспорт-пакет: признаки → синтетический датасет → training config → pipeline.

> **Статус:** bootstrap (День 1). Каркас репозитория, методология и локальный стек на месте. Код агентов, RAG-контент и тесты заполняются последующими задачами. См. [docs/implementation-plan/](docs/implementation-plan/).

## Быстрые ссылки

- [CLAUDE.md](CLAUDE.md) — правила для AI-ассистентов, работающих в этом репозитории
- [AGENTS.md](AGENTS.md) — реестр агентов
- [docs/00-methodology/](docs/00-methodology/) — как мы работаем (читать в первую очередь)
- [docs/00-methodology/repository-map.md](docs/00-methodology/repository-map.md) — где что лежит
- [examples/demo-langgraph-reviewer/](examples/demo-langgraph-reviewer/) — legacy demo planner/worker/reviewer

## Стек

Python 3.12, FastAPI, LangGraph, Ollama (`llama3.2`), Qdrant, PostgreSQL, MinIO, Pydantic v2, Docker Compose.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
make install-dev
```

## Уровни отладки

Проект спроектирован так, чтобы быть отлаживаемым **на любой глубине** — можно итерировать по одной функции без поднятия полного стека или запустить полный Compose, когда нужно. Выбирайте самый низкий уровень, который воспроизводит вашу проблему.

### Уровень 0 — Один модуль

Запустить файл схемы или валидатора напрямую. Полезно при редактировании Pydantic-контрактов.

```bash
python -m pydantic.tools schemas/context_memory.py   # скрипт валидации (когда появится)
python -c "from schemas.feature_spec import FeatureSpec; print(FeatureSpec.model_json_schema())"
```

### Уровень 1 — Unit-тесты

Чистые функции, схемы, валидаторы. Без I/O, без LLM.

```bash
make test-unit
# или один файл:
python -m pytest tests/unit/test_context_memory_schema.py -q
```

### Уровень 2 — Component-тесты

Один агент или один сервис с **фейками** для LLM и RAG. Без сети.

```bash
make test-component
python -m pytest tests/component/test_feature_synthesis_agent.py -q
```

### Уровень 3 — Оценка промптов и RAG

Модель и retrieval-политики прогоняются по записанным кейсам.

```bash
make test-prompt
make test-rag
```

### Уровень 4 — Интеграция локально (без контейнеров)

FastAPI + LangGraph + RAG + **замоканная LLM**, всё in-process. Ловит ошибки разводки без расхода ресурсов на локальную модель.

```bash
make test-integration
```

### Уровень 5 — Локальный API против локального Ollama

Приложение работает на хосте; Ollama и (опционально) Qdrant/Postgres/MinIO — в Docker. Лучший вариант для интерактивной отладки в VS Code.

```bash
make up-infra        # postgres + qdrant + minio
make up-llm          # ollama (пропустите, если ollama стоит нативно)
make run-api-reload  # uvicorn с hot reload — ставьте breakpoints в VS Code
```

Health-check:

```bash
curl -s http://127.0.0.1:8000/health
```

### Уровень 6 — Полный стек Compose

Всё в контейнерах, ближайшее приближение к production. Используется для проверки Dockerfile и разводки сервисов.

```bash
make up-all
# свернуть (также удаляет volumes):
make down
```

### Уровень 7 — Сквозной smoke-тест

Прогоняет полный пользовательский поток: brief → признаки → generation spec → датасет → экспорт.

```bash
make smoke
```

### Бонус — Legacy demo reviewer

Оригинальная LangGraph planner/worker/reviewer всё ещё работает как отдельный контейнер. Полезна как известный рабочий референс для «LangGraph + Ollama plumbing».

```bash
make demo-up
curl -s http://localhost:8000/health
make demo-down
```

См. [examples/demo-langgraph-reviewer/](examples/demo-langgraph-reviewer/).

## VS Code

`.vscode/launch.json` содержит готовые конфигурации отладки для нескольких уровней выше (один тестовый файл, FastAPI с reload, выбор pytest, legacy demo). Откройте панель Run & Debug и выберите подходящий конфиг.

## Поток разработки

1. Прочитать [docs/00-methodology/development-process.md](docs/00-methodology/development-process.md).
2. Выбрать или создать задачу в [docs/implementation-plan/](docs/implementation-plan/).
3. Сначала обновить docs и schemas, затем тесты, затем код.
4. Запустить соответствующую цель `make test-*`.
5. Обновить [docs/traceability/](docs/traceability/).

## Лицензия

Proprietary — для внутреннего использования.
