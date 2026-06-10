# Subagents FE-Bot

Project-level subagents Claude Code для полного цикла разработки FE-Bot — от бизнес-требований до кода, ревью и QA. Все агенты живут в `.claude/agents/` и доступны через `/agents` или явный вызов `Use the <agent-name> agent.`.

## Реестр

| # | Agent | Назначение | Tools | permissionMode |
| --- | --- | --- | --- | --- |
| 00 | [sdlc-coordinator](00-sdlc-coordinator.md) | Координирует lifecycle и направляет работу specialists | Read/Grep/Glob | plan |
| 01 | [business-analyst](01-business-analyst.md) | Сырые материалы → vision/goals/feature candidates | +Write/Edit | plan |
| 02 | [system-analyst](02-system-analyst.md) | Feature documents по 23-секционному шаблону | +Write/Edit | plan |
| 03 | [solution-architect](03-solution-architect.md) | C4 архитектура, ADR, service catalog | +Write/Edit | plan |
| 04 | [rag-architect](04-rag-architect.md) | RAG-методология, lifecycle, retrieval policies | +Write/Edit | plan |
| 05 | [langgraph-architect](05-langgraph-architect.md) | SetupGraph, RuntimeGraph, Review/Repair subgraphs | +Write/Edit | plan |
| 06 | [dto-contract-designer](06-dto-contract-designer.md) | DTO-01..53, API contracts, storage mapping | +Write/Edit | plan |
| 07 | [frontend-architect](07-frontend-architect.md) | Экраны, компоненты, state, UX | +Write/Edit | plan |
| 08 | [backend-architect](08-backend-architect.md) | Service boundaries, repository Protocols, workers | +Write/Edit | plan |
| 09 | [test-architect](09-test-architect.md) | 7 уровней тестов, golden datasets, coverage | +Write/Edit | plan |
| 10 | [implementation-planner](10-implementation-planner.md) | T-S01-XXX задачи, слайсы S0..S8 | +Write/Edit | plan |
| 11 | [code-implementer](11-code-implementer.md) | Реализация одной задачи + тесты + проверки | +Edit/Write/Bash, isolation: worktree | acceptEdits |
| 12 | [code-reviewer](12-code-reviewer.md) | Read-only review текущего diff | +Bash, **no** Edit/Write | plan |
| 13 | [rag-qa](13-rag-qa.md) | Retrieval metrics, validation, evidence coverage | +Bash, **no** Edit/Write | plan |
| 14 | [prompt-evaluator](14-prompt-evaluator.md) | Structured output, schema validity, hallucinations | +Bash, **no** Edit/Write | plan |
| 15 | [security-reviewer](15-security-reviewer.md) | Auth, upload, RAG isolation, secrets, audit | +Bash, **no** Edit/Write | plan |

## Принципы

### Один агент — одна роль

Не делать «суперагента». Архитектор не пишет код. Имплементер не меняет архитектуру. Reviewer не редактирует файлы.

### Read-only по умолчанию для аналитики и ревью

Архитекторы, ревьюеры и QA имеют `disallowedTools: Edit, Write, NotebookEdit` (или просто не получают эти tools). Это страховка от случайных правок.

### Worktree isolation для имплементера

`code-implementer` запускается с `isolation: worktree` — каждое его вмешательство уходит в отдельный git worktree. Подробнее — в [docs/00-methodology/](docs/00-methodology/) и в документации Claude Code.

### Контракт для имплементера

Code-implementer работает только по конкретной задаче T-S01-XXX из [docs/implementation-plan/](docs/implementation-plan/). Без задачи — отказ. Это enforced через системный prompt агента.

### Описания и промпты — по-русски

Тексты descriptions и системных prompts — на русском. Технические идентификаторы (имена классов, файлов, схем, агентов из AGENTS.md) — Latin, потому что они привязаны к коду.

## Эталонная цепочка для новой фичи

```
1. sdlc-coordinator         → определить текущую стадию и недостающие артефакты
2. business-analyst         → vision / feature candidate
3. system-analyst           → feature document по 23-секционному шаблону
4. solution-architect       → C4 контейнеры/компоненты + ADR
5. rag-architect            → RAG-методология (если RAG-фича)
6. langgraph-architect      → state machine (если Setup/Runtime workflow)
7. dto-contract-designer    → DTO + API/event contracts + storage
8. frontend-architect       → Frontend Scope §10
9. backend-architect        → Backend Scope §11
10. test-architect          → test plan §21
11. implementation-planner  → T-S01-XXX задачи
12. code-implementer        → реализация по слайсам S0..S8
13. code-reviewer           → review каждого PR
14. rag-qa + prompt-eval    → проверка качества RAG и LLM-агентов
15. security-reviewer       → перед релизом и при touch-and-go security-зон
```

## Примеры вызова

### Координация

```
Use the sdlc-coordinator agent.

Нужно реализовать SETUP-02 Document Upload.
Определи текущую стадию lifecycle, недостающие артефакты и какого агента запускать следующим.
```

### Feature document

```
Use the system-analyst agent.

Создай docs/02-system/features/SETUP-02-document-upload.md по 23-секционному шаблону.
Контекст: @docs/02-system/features/SETUP-01-setup-wizard.md
Код не создавать.
```

### Implementation task

```
Use the code-implementer agent.

Реализуй только T-S01-012 Document Upload Service из docs/implementation-plan/SETUP-01.tasks.md.

Перед изменениями:
1. Покажи план.
2. Перечисли target files.
3. Укажи тесты.

Не меняй frontend, LangGraph и DTO кроме перечисленных в задаче.
```

### Review

```
Use the code-reviewer agent.

Проверь текущий git diff против:
@docs/02-system/features/SETUP-01-setup-wizard.md
@docs/implementation-plan/SETUP-01.tasks.md

Не редактируй файлы.
```

### RAG QA

```
Use the rag-qa agent.

Прогон validation + retrieval smoke tests на текущей KB.
Отчёт по recall@5, precision@5, no_context_rate.
Не редактируй карточки.
```

## Tool policy

| Категория | Допустимые tools |
| --- | --- |
| Coordinator | Read, Grep, Glob |
| Architects (01-10) | Read, Grep, Glob, Write, Edit |
| Implementer (11) | Read, Grep, Glob, Edit, Write, Bash; `isolation: worktree` |
| Reviewers (12-15) | Read, Grep, Glob, Bash; `disallowedTools: Edit, Write, NotebookEdit` |

## Эволюция реестра

При добавлении нового агента:

1. Создать файл `.claude/agents/NN-<name>.md` по образцу.
2. Добавить строку в таблицу выше.
3. Если агент координируется через `sdlc-coordinator` — добавить упоминание в [00-sdlc-coordinator.md](00-sdlc-coordinator.md).
4. Если агент использует skill — упомянуть в `skills:` секции frontmatter.

## Связанные документы

- [.claude/skills/](../skills/) — повторяемые процедуры (ingest-docs, generate-rag-cards, generate-agent-contracts).
- [CLAUDE.md](../../CLAUDE.md) — проектная память.
- [AGENTS.md](../../AGENTS.md) — реестр **LLM-агентов** runtime-системы (другой класс агентов, не subagents Claude Code).
- [docs/00-methodology/](../../docs/00-methodology/) — методология разработки.
- [docs/implementation-plan/](../../docs/implementation-plan/) — задачи реализации.

## Различие: subagents Claude Code vs LLM-агенты FE-Bot

Не путать:

- **Subagents Claude Code** (этот каталог `.claude/agents/`) — помощники разработки в VS Code. Они пишут docs, проектируют, ревьюят код.
- **LLM-агенты FE-Bot** ([AGENTS.md](../../AGENTS.md)) — runtime-агенты приложения (`NLUAgent`, `FeatureSynthesisAgent`, etc.), которые работают в LangGraph и обрабатывают пользовательские диалоги.

Subagents здесь **проектируют и проверяют** LLM-агентов FE-Bot, но не являются ими.
