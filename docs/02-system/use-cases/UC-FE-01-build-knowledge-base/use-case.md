# UC-FE-01. Построение базы знаний с нуля

## Фичи

- [SETUP-01](../../features/SETUP-01-setup-wizard.md) Мастер настройки
- [SETUP-02..SETUP-13](../../features/feature-index.md) — фазы внутри мастера (включая классификацию секций — SETUP-13, замещающую SETUP-12)

## Основной актор

RAG Knowledge Base Admin (на ранней стадии — ML-инженер в роли админа).

## Поддерживающие акторы

- Доменный SME (опционально, на ревью)
- Локальная LLM (Ollama, `llama3.2`) — внутри RAG Card Generator
- Embedding-модель + Qdrant — внутри Embeddings & Index

## Предусловия

- Система установлена локально (`make install-dev`).
- Локальные сервисы доступны (Ollama, Qdrant, PostgreSQL, MinIO).
- Пользователь имеет на руках набор доменных документов (Markdown / PDF / DOCX / XLSX / CSV / JSON).
- Активная KB ещё не опубликована (Runtime заблокирован).

## Триггер

Пользователь открывает экран **Setup** и нажимает **«Создать новую базу знаний»**.

## Основной поток

1. Мастер создаёт `knowledge_base_session_id` и инициализирует пустой реестр источников.
2. Пользователь перетаскивает в зону загрузки папку с доменными документами. UI per-file показывает приём/отклонение.
3. Принятые файлы появляются в Source Registry со статусом `uploaded`. Пользователь может посмотреть metadata каждого.
4. Пользователь нажимает **«Build Knowledge Base»**. Мастер ставит сессию в состояние `running` и переходит в фазу **Parsing**.
5. Document Parser извлекает из каждого документа дерево секций. UI показывает per-document счётчики (sections found, errors).
6. Мастер переходит в фазу **RAG card generation**. RAG Card Generator через `LLM Gateway` черновикует одну карточку на секцию, проставляет metadata, оценивает `confidence_level`.
7. Metadata Validator (выполняется параллельно с генерацией) валидирует каждую карточку и помечает invalid-карточки.
8. Мастер переходит в фазу **Card review**. Пользователь открывает list, фильтрует по `doc_type`, для low-confidence/invalid карточек выбирает: **Approve**, **Edit + Approve**, **Reject**, **Regenerate**.
9. Когда все карточки помечены `approved` или `rejected`, мастер переходит в фазу **Chunking**. Chunking Service строит chunks (`definition`, `formula`, `examples`, …) и записывает `chunk_manifest.jsonl`.
10. Фаза **Embeddings & Index**: Embedding Service считает 384-мерные вектора, Vector DB Indexer заливает их в Qdrant под новую `index_version`. Эта `index_version` ещё неактивна.
11. Фаза **Retrieval smoke tests**: RAG Evaluation Service прогоняет курируемые запросы. Пользователь видит per-query `recall@k`, `precision@k`, статус.
12. На полностью green-отчёте мастер показывает **Publish Knowledge Base** с summary. Пользователь подтверждает.
13. Knowledge Base Registry назначает новую `kb_version` активной, замораживает её содержимое и эмитит уведомление **«Knowledge Base ready»**.
14. UI разблокирует точку входа Runtime.

## Альтернативные потоки

### A1. Парсер падает на отдельном документе

Document Parser помечает документ статусом `error` в Source Registry с конкретной причиной. Пользователь может: удалить документ, заменить файлом другого формата, или пропустить — мастер продолжает с остальными.

### A2. Сгенерированная карточка получает `confidence_level: low`

Карточка автоматически попадает в Review со статусом `review_required`. Мастер блокирует переход в Chunking, пока такие карточки не обработаны.

### A3. Metadata Validator отклоняет карточку

Карточка помечается `invalid` со списком ошибок (отсутствует `doc_id`, неизвестный `doc_type`, `domain` не в онтологии и т. п.). Пользователь правит inline; перевалидация запускается автоматически.

### A4. Retrieval smoke tests падают

UI показывает падающие запросы, отсутствующие ожидаемые `doc_id`-ы и неожиданные top-K попадания. Пользователь может: вернуться в Review (одобрить дополнительные карточки), регенерировать конкретные карточки, или (с записанным обоснованием) одобрить публикацию вопреки порогам.

### A5. Прерывание мастера

При перезаходе мастер восстанавливает фазу с последнего checkpoint-а (per-phase snapshot), не теряя загруженные документы, сгенерированные карточки или статусы ревью.

## Постусловия

- Активная `kb_version` установлена в Knowledge Base Registry.
- Векторный индекс под этой версией доступен `RAG Retrieval Service`-у.
- Source Registry содержит все исходные документы со статусами `processed`.
- RAG Card Registry содержит approved-карточки, связанные с исходниками.
- Audit Service содержит запись `kb_published`.
- Runtime-точка входа доступна.

## Связанные агенты / сервисы

- Setup Orchestrator, Document Upload Service, Source Registry Service, Document Parser, RAG Card Generator (через LLM Gateway), Metadata Validation Service, Card Review UI, Chunking Service, Embedding Service, Vector DB Indexer, RAG Evaluation Service, Knowledge Base Registry, Notification Service, Audit Service.

## Связанные контракты

- `UploadedDocument`, `SourceDocument`, `ParsedSection`, `RAGCardDraft`, `RAGCardReviewAction`, `RAGMetadataValidationReport`, `RAGChunk`, `ChunkManifest`, `EmbeddingJob`, `IndexCollection`, `RetrievalEvalReport`, `KnowledgeBaseVersion`.
