# Ingestion pipeline

## Назначение

Описать поток превращения сырых документов из `incoming-docs/raw/` в опубликованную базу знаний. Реализация — в Setup-стадии (см. [SETUP-01..SETUP-11](../02-system/features/feature-index.md)).

## Высокоуровневая последовательность

```text
incoming-docs/raw/                (сырые файлы)
        │
        ▼
SourceDocument                    (Source Registry; SETUP-02..03)
        │
        ▼
ParsedSection                     (Document Parser; SETUP-04)
        │
        ▼
RAGCardDraft                      (RAG Card Generator; SETUP-05)
        │
        ▼   review + edit + regenerate
RAGCard.approved                  (Card Review UI; SETUP-06)
        │
        ▼
ValidatedCard                     (Metadata Validator; SETUP-07)
        │
        ▼
RAGChunk + chunk_manifest.jsonl   (Chunking Service; SETUP-08)
        │
        ▼
Embeddings + Vector Index         (Embedding Service + Indexer; SETUP-09)
        │
        ▼
RetrievalEvalReport               (RAG Evaluation Service; SETUP-10)
        │
        ▼   passes thresholds
KnowledgeBaseVersion.active       (Knowledge Base Registry; SETUP-11)
```

## Обязательные инварианты

- Каждая карточка цитирует `source_document_ids` и `source_section_ids`.
- Каждый чанк наследует metadata карточки.
- Никакая карточка не индексируется без `status=approved` и `metadata_validator.passed`.
- Активная `kb_version` иммутабельна (INV-KB-002).

## Идемпотентность

- Повторная загрузка того же файла (по checksum) — no-op (INV-ID-001).
- Повторный парсинг того же документа сохраняет `source_document_id` и `section_id`.
- Повторное чанкование детерминировано → `chunk_id` стабилен (INV-ID-003).
- Повторный embedding на неизменённом chunk_manifest даёт байт-идентичные вектора (для фиксированной embedding-model).

## Ограничения

- Опубликованная KB-версия не модифицируется. Все правки идут через новую версию.
- Setup-сессия persists per-phase snapshot — прерывание мастера resumable.

## Roles

| Шаг | Кто отвечает |
| --- | --- |
| Загрузка | Пользователь (RAG admin) |
| Парсинг | Система |
| Card Generation | Система (LLM) |
| Card Review | Пользователь / SME |
| Metadata Validation | Система |
| Chunking | Система |
| Embedding + Indexing | Система |
| Retrieval Eval | Система + curated eval suite |
| Publication | Пользователь (явное подтверждение) |

## Связанные документы

- [rag-overview.md](rag-overview.md)
- [metadata-schema.md](metadata-schema.md)
- [chunk-schema.md](chunk-schema.md)
- [../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md](../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md)
- [../03-architecture/c4-component-setup-orchestrator.md](../03-architecture/c4-component-setup-orchestrator.md)
