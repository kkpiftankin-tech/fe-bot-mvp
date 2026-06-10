# Планы реализации

Этот каталог содержит нумерованные списки задач. Каждый план — Markdown-файл с именем `<scope>.tasks.md`. Задачи ссылаются на docs, schemas и тесты, которые они трогают.

## Соглашения

- ID задач стабильны: `T-<AREA>-<NNN>`. Area-коды:
  - `SETUP` — мастер базы знаний (Setup-стадия)
  - `MA` — multi-agent runtime
  - `AN` — analytics
  - `PL` — platform (API, LangGraph, контракты, storage)
  - `RAG` — retrieval, карточки, ingestion
  - `INFRA` — Compose, Dockerfiles, скрипты
  - `OBS` — observability, runbooks
- План «активный», если у него есть невыполненные задачи. Закрытые планы остаются в этом каталоге для истории.
- Новые планы создаются через `.claude/skills/create-implementation-plan/SKILL.md`.

## Текущие планы

| Plan | Scope | Status |
| --- | --- | --- |
| `FE-BOT-MVP.tasks.md` | MVP от bootstrap до первого сквозного экспорта | drafted |

См. [docs/00-methodology/artifact-templates.md](../00-methodology/artifact-templates.md#задача-реализации-docsimplementation-planplantasksmd) для шаблона задачи.
