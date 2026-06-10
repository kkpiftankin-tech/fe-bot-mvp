# SETUP-08. Генерация чанков

## Назначение

Превратить одобренные RAG-карточки в логические единицы, которые сохранит векторный индекс. Карточка обычно даёт несколько чанков (`definition`, `inputs`, `outputs`, `formula`, `validation_rules`, `examples`, `agent_usage` и др.), у каждого своя metadata и embedding-текст, оптимизированный под retrieval.

## Бизнес-ценность

Embedding целой карточки даёт один размытый вектор. Embedding хорошо типизированных чанков позволяет retrieval целиться в нужный слот, который нужен агенту (например, *только* `formula`-чанк `feature_pattern.signal_quality.v1`), и драматически улучшает recall.

## Пользовательский сценарий

1. Мастер переходит в фазу **Chunking**.
2. Per-карточка пользователь видит, сколько чанков произведено и каких типов.
3. Preview-панель позволяет открыть любой чанк и убедиться, что `embedding_text` не слишком длинный и несёт правильную metadata.

## Связанные требования

- BR-FR-Setup-081..084 (per-type чанкование, политика embedding-текста, стабильность chunk-id, эмиссия manifest).
- Схема чанка определена в [../../06-rag/chunk-schema.md](../../06-rag/chunk-schema.md).

## Связанные сервисы

- Chunking Service, RAG Card Registry, Chunk Manifest Builder, Frontend Chunk Preview UI, API Backend, Artifact Storage.

## Связанные контракты

- `RAGChunk` (`schemas/rag_chunks.py`): `chunk_id`, `doc_id`, `chunk_type`, `phase`, `slot`, `retrieval_purpose`, `embedding_text`, `priority`, `required_fields`.
- `ChunkManifest` (`rag/manifests/chunk_manifest.jsonl`): одна JSON-строка на чанк для нижестоящей индексации.

## Критерии приёмки

- `chunk_id` ОБЯЗАН быть стабильным между перечанкованиями того же контента карточки.
- Каждый чанк ОБЯЗАН наследовать `domain`, `task_type`, `data_source` родительской карточки.
- Манифест чанков ОБЯЗАН быть детерминированным для фиксированного набора карточек.
- Тест: `tests/component/test_setup_chunking.py`.
