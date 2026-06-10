# Стратегия тестирования

## Уровни тестов

| Уровень | Что проверяется | Изоляция | Каталог |
| --- | --- | --- | --- |
| Unit | Pydantic-схемы, валидаторы, чистые функции | без I/O, без LLM | [`tests/unit/`](../../tests/unit/) |
| Component | Один агент или один сервис с фейками LLM+RAG | без сети | [`tests/component/`](../../tests/component/) |
| Prompt eval | Реальная (или фейк-) LLM против golden cases | mock-RAG | [`tests/prompt_eval/`](../../tests/prompt_eval/) |
| RAG eval | Retrieval против curated queries | реальная Vector DB или встроенная | [`tests/rag_eval/`](../../tests/rag_eval/) |
| Integration | FastAPI ⇄ LangGraph ⇄ RAG ⇄ LLM-mock | без контейнеров | [`tests/integration/`](../../tests/integration/) |
| E2E | Полный пользовательский поток | Docker Compose | [`tests/e2e/`](../../tests/e2e/) |

## Принципы

- Unit-тесты не вызывают LLM и не ходят в сеть. Если кажется, что нужен LLM — выделите чистую функцию.
- Component-тесты используют фейк-LLM с записанными ответами (snapshot-based) для детерминизма.
- Prompt eval хранит golden cases (YAML) и регулярно прогоняется на дефолтной модели Ollama.
- RAG eval — публикуется только тогда, когда eval-сьют покрывает все retrieval-политики из [docs/06-rag/retrieval-policies.md](../06-rag/retrieval-policies.md).
- Integration-тесты гарантируют, что разводка LangGraph не сломалась, без расхода реального LLM-времени.
- E2E прогоняется на смоук-нагрузке (наш эталонный radar-сценарий) до релиза.

## Make-цели

```bash
make test-unit
make test-component
make test-prompt
make test-rag
make test-integration
make test-e2e
make smoke         # быстрый сквозной smoke
```

## Связанные документы

- [unit-tests.md](unit-tests.md)
- [component-tests.md](component-tests.md)
- [integration-tests.md](integration-tests.md)
- [e2e-tests.md](e2e-tests.md)
- [rag-evaluation.md](rag-evaluation.md)
- [prompt-evaluation.md](prompt-evaluation.md)
