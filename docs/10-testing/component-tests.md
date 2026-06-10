# Component-тесты

## Назначение

Проверить агента или один сервис в изоляции, с фейками LLM и RAG.

## Что покрывается

- Каждый агент из [AGENTS.md](../../AGENTS.md) — happy path + 1–2 граничных случая.
- Setup-сервисы (Document Parser, RAG Card Generator с fake-LLM, Metadata Validator, Chunking, Embedding с fake-model, Indexer с in-memory backend).
- Runtime-сервисы (Validation Worker, Data Generation Worker).

## Структура

```text
tests/component/
├── test_session_agent.py
├── test_nlu_agent.py
├── test_rag_retrieval_agent.py
├── test_task_discovery_agent.py
├── test_data_profiling_agent.py
├── test_domain_context_agent.py
├── test_feature_synthesis_agent.py
├── test_feature_critic_agent.py
├── test_multicollinearity_agent.py
├── test_data_generation_spec_agent.py
├── test_data_generation_worker.py
├── test_model_selection_agent.py
├── test_export_agent.py
├── test_setup_document_upload.py
├── test_setup_parser.py
├── test_setup_card_generation.py
├── test_setup_card_review.py
├── test_setup_validation_loop.py
├── test_setup_chunking.py
└── test_setup_embedding_indexing.py
```

## Фейк-LLM

Каждый тест-кейс хранит «запись ответа модели» — JSON-фикстура. Это исключает дрейф между LLM-апдейтами в component-слое.

## Запуск

```bash
make test-component
pytest tests/component/test_feature_synthesis_agent.py::test_happy_path -q
```
