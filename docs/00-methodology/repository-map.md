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
│   ├── 00-methodology/        # Как мы работаем + точка входа README.md (этот каталог)
│   ├── 01-business/           # Vision, цели, стейкхолдеры, ограничения, бизнес-требования, MVP
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
│   ├── implementation-plan/   # Нумерованные списки задач
│   ├── observability/         # Определения дашбордов (например, taxonomy-health.json)
│   └── tech-debt/             # Зафиксированный технический долг (TD-*)
│
├── rag/                       # Контент базы знаний RAG
│   ├── ontology/              # Онтологические карточки
│   ├── cards/                 # Карточки domain/schema/feature/analytics/validation
│   ├── manifests/             # document_index.json, chunk_manifest.jsonl
│   └── relationships/         # Связи между карточками + retrieval-политики
│
├── schemas/                   # Pydantic-схемы (контракты): setup/, rag/, taxonomy/, classifier/, common/
├── prompts/                   # Шаблоны промптов, по одному на агента
├── validators/                # Детерминированные проверки (источник истины)
│
├── config/                    # Конфигурация (например, config/taxonomy/auto_allocation.yaml)
├── seed/                      # Начальные данные: seed/taxonomy/ (таксономия), seed/classifier/ (дерево классификаторов)
├── frontend/                  # UI на React + TypeScript (Vite): Setup-мастер из 11 шагов
├── var/                       # Локальное состояние dev-окружения: снимок репозиториев и blob-хранилище (var/state/); в .gitignore
│
├── src/fe_bot/                # Код приложения
│   ├── api/                   # FastAPI app; api/setup/ — роутеры и DTO Setup-мастера
│   ├── setup/                 # Backend Setup: upload, source_registry, parser, rag_card_generation,
│   │                          #   card_review, metadata_validation, chunking, embedding, evaluation, publish
│   ├── taxonomy/              # Иерархическая таксономия секций (SETUP-12; замещена SETUP-13, код сохранён)
│   ├── classifier/            # Библиотека классификаторов (SETUP-13)
│   ├── llm_gateway/           # Клиент LLM (Ollama)
│   ├── vector_index/          # Работа с Qdrant
│   ├── storage/               # Artifact Storage (MinIO)
│   ├── persistence/           # Снапшоты состояния
│   ├── retrieval/             # Retrieval-сервис
│   ├── auth/                  # Роли и права (rag_admin, publish и др.)
│   ├── audit/                 # Audit-события
│   ├── observability/         # Логи, метрики, трейсинг
│   ├── graph/                 # Разводка LangGraph — Runtime, пока пусто
│   ├── agents/                # Реализации агентов — Runtime, пока пусто
│   ├── rag/                   # Evidence pack builder — Runtime, пока пусто
│   ├── tools/                 # Python-инструменты агентов — Runtime, пока пусто
│   ├── data_generation/       # Worker синтетических данных — Runtime, пока пусто
│   └── export/                # Сборка артефактов — Runtime, пока пусто
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
    ├── skills/                # Skills в стиле slash-команд для Claude Code
    └── agents/                # Специализированные субагенты проекта
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
| Добавить шаг или экран Setup-мастера | `frontend/src/components/Wizard/steps/` + роутер в `src/fe_bot/api/setup/` + логика в `src/fe_bot/setup/` |
| Добавить seed-данные (таксономия, классификаторы) | `seed/taxonomy/`, `seed/classifier/` |
| Зафиксировать технический долг | `docs/tech-debt/TD-<AREA>-<NNN>-<slug>.md` |

## Пустые каталоги

Пустые каталоги содержат файл-заглушку `.gitkeep`. Заменяйте его реальным контентом, как только каталог становится несущим.

## Смотри также

- [README.md](README.md) — что за система и как читать документацию.
- [development-process.md](development-process.md) — порядок появления артефактов.
- [traceability-rules.md](traceability-rules.md) — как поддерживается честность связей между артефактами.
