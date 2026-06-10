# C4 — Уровень 3: Component (RAG Service)

## Назначение

Декомпозировать контейнер RAG Service: что он делает в Setup-стадии (генерация / индексация / eval) и в Runtime-стадии (retrieval).

## Диаграмма (Mermaid)

```mermaid
C4Component
  title RAG Service — Components

  Container_Boundary(rag, "RAG Service") {
    Component(retrieval_planner, "Retrieval Planner", "Python", "Собирает план запросов: метадата-фильтры + семантические запросы по фазе и слотам ContextMemory")
    Component(retriever, "Retriever", "Python", "Выполняет vector search с фильтрами против Qdrant, делает rerank")
    Component(evidence_assembler, "Evidence Assembler", "Python", "Собирает компактный EvidencePack для агента")
    Component(card_generator, "RAG Card Generator", "Python + LLM", "Из parsed-секции производит черновую карточку")
    Component(metadata_validator, "Metadata Validator", "Python", "Проверяет полноту metadata, соответствие онтологии, ссылки")
    Component(chunking_service, "Chunking Service", "Python", "Из approved-карточек строит RAGChunk + chunk_manifest")
    Component(embedding_client, "Embedding Client", "Python", "Считает 384-мерные embeddings (sentence-transformer)")
    Component(indexer, "Vector DB Indexer", "Python", "Bulk insert/update в Qdrant по collections")
    Component(eval_runner, "Retrieval Evaluation Runner", "Python", "Прогоняет curated eval queries, считает recall@k / precision@k")
    Component(card_registry, "RAG Card Registry", "Python", "CRUD по карточкам, версионирование, статусы")
    Component(kb_registry, "Knowledge Base Registry", "Python", "Активная kb_version, иммутабельность опубликованных KB")
  }

  ContainerDb_Ext(qdrant, "Qdrant Vector DB", "Qdrant")
  ContainerDb_Ext(postgres, "PostgreSQL", "Postgres 16")
  ContainerDb_Ext(minio, "MinIO", "S3-совместимое")
  Container_Ext(llm_gateway, "LLM Gateway", "Python")
  Container_Ext(setup_orch, "Setup Orchestrator", "Python")
  Container_Ext(agent_runtime, "Agent Runtime", "Python")

  Rel(agent_runtime, retrieval_planner, "запрос evidence")
  Rel(retrieval_planner, retriever, "построенный план")
  Rel(retriever, qdrant, "vector search + filters", "gRPC")
  Rel(retriever, evidence_assembler, "raw hits")
  Rel(evidence_assembler, agent_runtime, "EvidencePack")

  Rel(setup_orch, card_generator, "generate(parsed_section)")
  Rel(card_generator, llm_gateway, "structured output")
  Rel(card_generator, card_registry, "save draft")
  Rel(setup_orch, metadata_validator, "validate(card)")
  Rel(metadata_validator, card_registry, "пометить valid/invalid")
  Rel(setup_orch, chunking_service, "build chunks(approved_cards)")
  Rel(chunking_service, minio, "chunk_manifest.jsonl")
  Rel(setup_orch, embedding_client, "embed(chunks)")
  Rel(embedding_client, indexer, "vectors + metadata")
  Rel(indexer, qdrant, "upsert", "gRPC")
  Rel(setup_orch, eval_runner, "run eval suite")
  Rel(eval_runner, qdrant, "vector search", "gRPC")
  Rel(setup_orch, kb_registry, "publish kb_version")
  Rel(kb_registry, postgres, "active kb pointer", "SQL")
  Rel(card_registry, postgres, "card + version state", "SQL")
```

## Компоненты

### Retrieval Planner

По текущей фазе и `ContextMemory` строит `RetrievalPlan` — набор подзапросов с metadata-фильтрами (`doc_type`, `phase`, `domain`, `task_type`, `data_source`) и семантическими запросами. Один шаг пользователя может породить несколько подзапросов (например, в `feature_synthesis` — отдельно к `feature_pattern`, `analytics_card`, `schema_card`).

### Retriever

Выполняет план через Qdrant. Делает rerank top-K hits по metadata-сигналам (`confidence_level`, `priority`, `recency`).

### Evidence Assembler

Собирает компактный `EvidencePack`, который агент сможет уместить в контекстное окно (4k–8k токенов). Включает `evidence_doc_ids` для последующей цитации.

### RAG Card Generator

Setup-стадия. По parsed-секции через LLM Gateway черновикует одну карточку соответствующего семейства, проставляет metadata из секции + онтологии.

### Metadata Validator

Детерминированно проверяет: обязательные поля, словари допустимых значений (онтология), целостность ссылок (`source_document_id`, `evidence_doc_ids`).

### Chunking Service

Из approved-карточки производит чанки (`definition`, `inputs`, `outputs`, `formula`, `validation_rules`, `examples`, ...). Эмитит `chunk_manifest.jsonl`.

### Embedding Client

Считает 384-мерные embeddings. Может работать против локального sentence-transformer или прокидывать вызов в Ollama (если выбран embeddings-pathway через Ollama).

### Vector DB Indexer

Bulk upsert чанков с metadata в Qdrant. Изолирует ошибки per-chunk, ведёт `IndexCollection`.

### Retrieval Evaluation Runner

Прогоняет курируемый eval-suite (queries + expected `doc_ids`) против новой `index_version`, считает `recall@k` / `precision@k`. Используется в [SETUP-10](../02-system/features/SETUP-10-retrieval-tests.md).

### RAG Card Registry / Knowledge Base Registry

Stateful слой над PostgreSQL. Версионирует карточки, статусы, KB-версии. Только Knowledge Base Registry знает, какая версия — `active`.

## Связанные документы

- [c4-container.md](c4-container.md)
- [c4-component-agent-runtime.md](c4-component-agent-runtime.md)
- [../06-rag/rag-overview.md](../06-rag/rag-overview.md)
- [../06-rag/retrieval-policies.md](../06-rag/retrieval-policies.md)
- [../06-rag/evidence-pack.md](../06-rag/evidence-pack.md)
