# ADR-003. Qdrant как векторная БД

## Status

Accepted

## Context

Системе нужна векторная БД, которая:

- работает локально (NFR-Port-001, C-07),
- поддерживает фильтры по metadata (`doc_type`, `phase`, `domain`, `task_type`, `data_source`),
- укладывается в latency 50 мс p95 на эталонной нагрузке ~10k чанков (NFR-Perf-002),
- имеет питоновский клиент и docker image.

Альтернативы:

1. **FAISS in-process.** Сверхбыстро, но: только in-memory, без metadata-фильтрации из коробки, без HTTP-протокола.
2. **Chroma.** Простой и pythonic, но менее зрелый по metadata-фильтрам и multi-collection семантике.
3. **Weaviate.** Мощный, но тяжелее по ресурсам, сложнее в локальной разработке.
4. **pgvector в PostgreSQL.** Один сервис вместо двух, но: фильтрация по metadata требует ручных SQL, hybrid search хуже; для laptop-scale выигрыш есть, но цена поддержки специальных индексов выше.
5. **Qdrant.** Лёгкий, hybrid-search-friendly, metadata-фильтры на уровне API, gRPC-протокол.

## Decision

По умолчанию использовать Qdrant. Одна коллекция на семейство карточек (`domain_profiles`, `schema_cards`, `feature_patterns`, `analytics_cards`, `validation_rules`, `question_templates`, `glossary`, `examples`) с общими metadata-полями.

## Consequences

- Положительные:
  - Metadata-фильтрация и rerank на стороне БД (а не post-process).
  - Поддерживает per-collection индексы; легко версионировать `index_version`.
  - Локальный Docker-image; minimal footprint.
- Отрицательные:
  - Ещё один сервис (vs. all-in-one pgvector).
  - Backup / restore поверх StatefulSet — отдельная процедура.
- Нейтральные:
  - Команды индексации и поиска инкапсулированы в `RAG Service`; смена БД сводится к замене адаптера.

## Related

- [../c4-container.md](../c4-container.md)
- [../c4-component-rag-service.md](../c4-component-rag-service.md)
- [../../06-rag/rag-overview.md](../../06-rag/rag-overview.md)
- [../../06-rag/retrieval-policies.md](../../06-rag/retrieval-policies.md)
