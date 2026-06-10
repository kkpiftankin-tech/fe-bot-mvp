# Карта репозитория

Эта страница — единый источник истины о том, **где что лежит**. Если каталог отсутствует или пуст, сначала добавьте сюда заглушку, а потом создайте его.

## Верхнеуровневая структура

```text
repo/
├── CLAUDE.md                  # Проектная память AI-ассистента
├── AGENTS.md                  # Реестр агентов
├── README.md                  # Точка входа для людей + уровни отладки
├── Makefile                   # Локальные команды (тесты, стек, smoke, валидация)
├── pyproject.toml             # Метаданные Python-проекта + зависимости
│
├── incoming-docs/             # Сырые материалы, проходящие ingestion
│   ├── index.md
│   └── raw/
│
├── docs/                      # Вся документация
│   ├── 00-methodology/        # Как мы работаем (этот каталог)
│   ├── 01-business/           # Vision, цели, стейкхолдеры, ограничения
│   ├── 02-system/             # System overview, фичи, use cases, FR/NFR
│   ├── 03-architecture/       # C4-виды + ADR
│   ├── 04-domain/             # Доменная модель, сущности, инварианты
│   ├── 05-agents/             # По одной спецификации на агента
│   ├── 06-rag/                # Онтология RAG, схемы документов/чанков, политики
│   ├── 07-contracts/          # Pydantic-контракты (зеркало schemas/)
│   ├── 08-data/               # Модели source/generated/feature-store данных
│   ├── 09-langgraph/          # State machine, узлы, переходы, repair loops
│   ├── 10-testing/            # Стратегия тестирования и руководства по слоям
│   ├── 11-operations/         # Наблюдаемость, метрики, развёртывание, runbooks
│   ├── traceability/          # Матрицы покрытия между артефактами
│   └── implementation-plan/   # Нумерованные списки задач
│
├── rag/                       # Контент базы знаний RAG
│   ├── ontology/              # Онтологические карточки
│   ├── cards/                 # Карточки domain/schema/feature/analytics/validation
│   ├── manifests/             # document_index.json, chunk_manifest.jsonl
│   └── relationships/         # Связи между карточками + retrieval-политики
│
├── schemas/                   # Pydantic-схемы (контракты)
├── prompts/                   # Шаблоны промптов, по одному на агента
├── validators/                # Детерминированные проверки (источник истины)
│
├── src/fe_bot/                # Код приложения
│   ├── api/                   # FastAPI app
│   ├── graph/                 # Разводка LangGraph
│   ├── agents/                # Реализации агентов
│   ├── rag/                   # Retriever + evidence pack builder
│   ├── tools/                 # Python-инструменты, которые вызывают агенты
│   ├── data_generation/       # Worker синтетических данных
│   ├── export/                # Сборка артефактов
│   └── observability/         # Логи, метрики, трейсинг
│
├── tests/
│   ├── unit/                  # Схемы, валидаторы, утилиты
│   ├── component/             # Один агент или один сервис с фейками
│   ├── integration/           # FastAPI ⇄ LangGraph ⇄ RAG ⇄ LLM mock
│   ├── e2e/                   # Полный happy path
│   ├── rag_eval/              # Качество retrieval
│   └── prompt_eval/           # Prompt → schema-valid JSON
│
├── infra/
│   ├── compose/               # docker-compose.yml с профилями
│   └── docker/                # Dockerfiles по сервисам
│
├── scripts/
│   ├── docs/                  # Валидация traceability
│   ├── rag/                   # Валидация карточек, сборка индекса
│   ├── smoke/                 # Сквозные smoke-проверки
│   └── dev/                   # Локальные удобные запускалки
│
├── examples/
│   └── demo-langgraph-reviewer/  # Legacy demo planner/worker/reviewer
│
└── .claude/
    └── skills/                # Skills в стиле slash-команд для Claude Code
```

## Куда класть что

| Если нужно... | Положить сюда |
| --- | --- |
| Документировать нового агента | `docs/05-agents/<agent-name>.md` + строка в [AGENTS.md](../../AGENTS.md) |
| Определить структуру вывода агента | `schemas/agent_outputs.py` или отдельный файл в `schemas/` |
| Добавить RAG-карточку | `rag/cards/<card-family>/<card-id>.yaml` |
| Добавить детерминированную проверку | `validators/<topic>_validator.py` |
| Добавить тест на одного агента | `tests/component/test_<agent>.py` |
| Добавить спецификацию фичи | `docs/02-system/features/<ID>-<slug>.md` |
| Добавить use case | `docs/02-system/use-cases/UC-FE-XX-<slug>/use-case.md` |
| Зафиксировать архитектурное решение | `docs/03-architecture/adr/ADR-XXX-<slug>.md` |
| Добавить Compose-сервис или профиль | `infra/compose/docker-compose.yml` |
| Обновить agent-to-contract map | `docs/traceability/agent-to-contract-map.md` |

## Пустые каталоги

Пустые каталоги содержат файл-заглушку `.gitkeep`. Заменяйте его реальным контентом, как только каталог становится несущим.

## Смотри также

- [development-process.md](development-process.md) — порядок появления артефактов.
- [traceability-rules.md](traceability-rules.md) — как поддерживается честность связей между артефактами.
