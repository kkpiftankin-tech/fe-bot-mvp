# Integration-тесты

## Назначение

Убедиться, что разводка `FastAPI ⇄ LangGraph ⇄ Agent Runtime ⇄ RAG ⇄ LLM-mock ⇄ Validation Worker` работает без реальных контейнеров.

## Что покрывается

- API-контракты (`tests/integration/test_api_contracts.py`).
- LangGraph state machine: переходы по фазам, repair-loops, HITL-interrupts (`tests/integration/test_langgraph_state_machine.py`).
- Полный data-generation flow с реальным `DataGenerationWorker` и `ValidationWorker` (`tests/integration/test_data_generation_flow.py`).
- Setup happy path с in-memory VectorDB-фейком (`tests/integration/test_setup_pipeline.py`).

## Окружение

- PostgreSQL — in-memory (SQLite-совместимая прослойка) или эпhemeral testcontainer.
- Vector DB — in-process fake (Python-словарь с metadata-фильтрацией).
- LLM — fake-bridge с записанными ответами.

## Запуск

```bash
make test-integration
```
