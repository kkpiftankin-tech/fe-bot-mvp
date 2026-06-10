# PLATFORM-02. LangGraph Orchestrator

## Назначение

State machine, движущая Runtime: маршрутизирует шаг пользователя к нужному агенту по текущей фазе, продвигает фазу при выполнении completion-criteria, гоняет repair-loops при сбое валидации и персистит checkpoints `ContextMemory` между переходами.

## Бизнес-ценность

Без явной state machine шаг пользователя пришлось бы интерпретировать LLM каждый раз — медленно, хрупко, неуправляемо. Оркестратор делает workflow auditable и тестируемым изолированно.

## Пользовательский сценарий

Пользователь пишет шаг. Оркестратор смотрит на `ContextMemory.current_phase`, выбирает релевантного агента, вызывает его через `LLM Gateway`, валидирует вывод против Pydantic-схемы, пишет валидированный результат в `ContextMemory`, оценивает completion-criteria фазы и либо продвигает фазу, либо задаёт пользователю уточняющий вопрос — всё без решений по маршрутизации, принимаемых LLM.

## Связанные требования

- BR-FR-Conv-003 (детерминированное продвижение фазы).
- BR-FR-Sys-001..002 (Pydantic-валидация перед записью; ограниченные repair-loops, дефолт `max_retries = 3`).
- NFR-Rel-001..003 (repair, fallback, checkpointing).

## Связанные сервисы

- LangGraph Orchestrator, Agent Runtime, ContextMemory Service, Conversation DB, LLM Gateway, RAG Retrieval Service.

## Связанные контракты

- `LangGraphState` — это сама `ContextMemory`; узлы возвращают частичные обновления.
- Per-node Pydantic-выводы из `schemas/agent_outputs.py`.

## Критерии приёмки

- Узел, вернувший невалидный вывод, ОБЯЗАН триггерить repair-шаг с приложенным отчётом валидатора — не падать, не пропускать.
- Переходы фаз ОБЯЗАНЫ быть детерминированными при той же `ContextMemory`.
- Тест: `tests/integration/test_langgraph_state_machine.py`.
