# ADR-005. Трёхстадийная архитектура: Setup, Runtime, Analytics

## Status

Accepted

## Context

В ранней версии проекта Runtime-диалог считался единственной user-facing поверхностью; ingestion RAG-документов и аналитика подразумевались как «инфраструктурные» задачи без UI.

На практике это разваливается:

- Без UI-мастера Setup пользователь не знает, в каком состоянии его база знаний; ошибки парсинга и валидации видны только в логах.
- Без видимой аналитики drop-off-ы фаз и регрессии RAG-качества обнаруживаются «случайно».
- Audit trail без UI — это файл, который никто не читает.

## Decision

Структурировать систему как **три явные пользовательские стадии**, у каждой свой UI, свои метрики, свой реестр фич:

- **Setup** ([SETUP-01..SETUP-11](../../02-system/features/feature-index.md)).
- **Runtime** ([RUNTIME-01..RUNTIME-12](../../02-system/features/feature-index.md)).
- **Analytics** ([ANALYTICS-01..ANALYTICS-09](../../02-system/features/feature-index.md)).

Сквозные компоненты вынесены в `PLATFORM-XX`.

## Consequences

- Положительные:
  - Каждая стадия тестируется и релизится изолированно.
  - User-видимые предусловия (Setup → Runtime) делают невозможным «Runtime без KB».
  - Analytics — first-class, а не addon. RAG-качество не дрейфует молча.
  - Audit trail имеет владельца (Audit Service) и UI (ANALYTICS-09).
- Отрицательные:
  - Усложнение интерфейса: три точки входа вместо одной.
  - Setup-мастер требует поддержки HITL-флоу (review карточек) — это дополнительная сложность.
- Нейтральные:
  - Внутри Setup используется sequential pipeline, внутри Runtime — LangGraph state machine. Это две разные парадигмы оркестрации в одной системе (см. [ADR-001](ADR-001-langgraph-as-orchestrator.md)).

## Related

- [../../02-system/system-overview.md](../../02-system/system-overview.md)
- [../../01-business/vision.md](../../01-business/vision.md)
- [../c4-component-setup-orchestrator.md](../c4-component-setup-orchestrator.md)
