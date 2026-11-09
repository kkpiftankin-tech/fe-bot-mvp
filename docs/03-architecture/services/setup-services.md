# Сервисы настройки RAG-базы (SVC-04..SVC-15)

Сервисы стадии Setup. Полный пользовательский поток — в [UC-FE-01](../../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md).

---

## SVC-04. Setup Orchestrator

### Назначение

Управляет пользовательским workflow настройки RAG-базы: от загрузки документов до публикации активной Knowledge Base.

### Функции

Запускает и координирует фазы: upload validation, parsing, section extraction, RAG-card generation, metadata validation, chunking, embedding, indexing, retrieval tests, publish. Хранит per-phase snapshot и эмитит прогресс во frontend.

### DTO

`SourceDocumentDTO`, `ParsedSectionDTO`, `RAGCardDTO`, `ChunkDTO`, `VectorIndexDTO`, `ValidationReportDTO`, `AnalyticsEventDTO`.

### Внешние участники

EXT-01 пользователь-настройщик, EXT-02 RAG admin, EXT-03 SME.

### Соседние сервисы

SVC-02 API Gateway, SVC-05 Document Upload, SVC-06 Source Registry, SVC-07 Document Parser, SVC-09 RAG Card Generator, SVC-08 Ontology/Metadata, SVC-11 Chunking, SVC-12 Embedding, SVC-13 Vector Indexer, SVC-14 Retrieval Evaluation, SVC-15 KB Registry, SVC-37 Notification, SVC-36 Audit.

### Информационный обмен

С `SVC-05` — список загруженных документов.
С `SVC-07` — отправка документов на парсинг и parsed sections обратно.
С `SVC-09` — отправка секций и получение RAG-карточек.
С `SVC-08` — карточки на валидацию.
С `SVC-11` — подтверждённые карточки и chunks.
С `SVC-12`/`SVC-13` — запуск embedding и индексации.
С `SVC-14` — отчёт smoke-тестов.
С `SVC-15` — команды публикации.
С `SVC-37` — события прогресса.

### Входные данные

Команда «Сформировать RAG», список `source_document_id`, параметры проекта, active ontology version.

### Выходные данные

Setup status, progress events, processing report, validation errors, `knowledge_base_version`, финальный `ready` / `failed` / `review_required`.

### Реализует фичи

[SETUP-01](../../02-system/features/SETUP-01-setup-wizard.md) (и оркеструет [SETUP-02..SETUP-11](../../02-system/features/feature-index.md)).

---

## SVC-05. Document Upload Service

### Назначение

Приём, первичная проверка и сохранение исходных файлов.

### Функции

Валидация формата и размера, вычисление checksum, выявление дублей, сохранение файла в storage, создание первичной записи в Source Registry.

### DTO

`SourceDocumentDTO`, `UploadFileDTO`, `ValidationReportDTO`, `AuditEventDTO`.

### Внешние участники

EXT-01 пользователь, EXT-02 RAG admin.

### Соседние сервисы

SVC-02 API Gateway, SVC-38 Artifact Storage, SVC-06 Source Registry, SVC-36 Audit, SVC-37 Notification.

### Информационный обмен

С `SVC-02` — multipart upload. С `SVC-38` — бинарный файл на сохранение. С `SVC-06` — metadata файла. С `SVC-36` — событие `document_uploaded`. С `SVC-37` — событие `upload_completed`.

### Входные данные

Файл, имя, MIME-type, размер, теги, user id.

### Выходные данные

`SourceDocumentDTO`, storage path, checksum, upload status, ошибки.

### Реализует фичи

[SETUP-02](../../02-system/features/SETUP-02-document-upload.md).

---

## SVC-06. Source Registry Service

### Назначение

Реестр исходных документов и lineage от файла до RAG-карточки/chunk/vector index.

### Функции

Создаёт записи документов, обновляет статусы обработки, хранит связи `source_document → parsed_section → rag_card → chunk → embedding`.

### DTO

`SourceDocumentDTO`, `ParsedSectionDTO`, `RAGCardDTO`, `ChunkDTO`, `AuditEventDTO`.

### Внешние участники

EXT-02 RAG admin, EXT-03 SME, аудитор.

### Соседние сервисы

SVC-05 Document Upload, SVC-07 Document Parser, SVC-09 RAG Card Generator, SVC-11 Chunking, SVC-15 KB Registry, SVC-36 Audit, SVC-35 Analytics.

### Информационный обмен

С `SVC-05` — новые `SourceDocument`-ы. С `SVC-07` — `parsed_sections`. С `SVC-09` — связи `section ↔ rag_card`. С `SVC-11` — связи `rag_card ↔ chunk`. С `SVC-35` — статистика по источникам.

### Входные данные

Metadata документа, статусы обработки, связи артефактов, audit events.

### Выходные данные

Реестр документов, lineage graph, status summary, source-to-artifact trace.

### Реализует фичи

[SETUP-03](../../02-system/features/SETUP-03-source-registry.md).

---

## SVC-07. Document Parser Service

### Назначение

Извлечение текста и структуры из загруженных документов.

### Функции

Парсинг Markdown, PDF, DOCX, CSV, XLSX, JSON; выделение заголовков, таблиц, секций, JSON-блоков; нормализация текста и предполагаемый тип секции.

### DTO

`SourceDocumentDTO`, `ParsedSectionDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-01 пользователь (косвенно), EXT-02 RAG admin.

### Соседние сервисы

SVC-04 Setup Orchestrator, SVC-06 Source Registry, SVC-38 Artifact Storage, SVC-09 RAG Card Generator, SVC-36 Audit.

### Информационный обмен

С `SVC-38` — получение файла. С `SVC-04` — команды parse. С `SVC-06` — сохранение `parsed_sections`. С `SVC-09` — передача секций.

### Входные данные

`source_document_id`, путь к файлу, content type, raw content.

### Выходные данные

`ParsedSectionDTO`, normalized text, detected section type, parsing warnings, parse report.

### Реализует фичи

[SETUP-04](../../02-system/features/SETUP-04-document-parsing.md).

---

## SVC-08. Ontology and Metadata Service

### Назначение

Источник истины онтологии и валидатор metadata RAG-документов.

### Функции

Управляет словарями `domain`, `task_type`, `data_source`, `entity_type`, `doc_type`, `phase`, `feature_family`; валидирует metadata карточек и чанков; нормализует термины.

### DTO

`RAGMetadataDTO`, `OntologyTermDTO`, `ValidationReportDTO`, `ChunkDTO`.

### Внешние участники

EXT-02 RAG admin, EXT-03 SME.

### Соседние сервисы

SVC-09 RAG Card Generator, SVC-11 Chunking, SVC-21 RAG Retrieval, SVC-15 KB Registry, SVC-35 Analytics.

### Информационный обмен

С `SVC-09` — допустимые ontology terms. С `SVC-11` — chunk metadata schema. С `SVC-21` — фильтры retrieval. С `SVC-35` — статистика использования terms.

### Входные данные

Ontology definitions, RAG metadata, chunk metadata, пользовательские правки.

### Выходные данные

Validated metadata, normalized terms, validation errors, ontology version.

### Реализует фичи

[SETUP-07](../../02-system/features/SETUP-07-metadata-validation.md). Документация онтологии: [docs/06-rag/ontology.md](../../06-rag/ontology.md), [docs/06-rag/metadata-schema.md](../../06-rag/metadata-schema.md).

---

## SVC-09. RAG Card Generator

### Назначение

Превращает parsed sections в типизированные RAG-карточки.

### Функции

Классифицирует секции, формирует YAML front matter, генерирует Markdown body, присваивает `doc_id`, определяет `doc_type`, заполняет `retrieval_tags`, связывает карточку с источником.

### DTO

`ParsedSectionDTO`, `RAGCardDTO`, `RAGMetadataDTO`, `AgentRequestDTO`, `AgentResponseDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-02 RAG admin, EXT-03 SME, EXT-07 локальная LLM.

### Соседние сервисы

SVC-04 Setup Orchestrator, SVC-07 Document Parser, SVC-08 Ontology, SVC-20 LLM Gateway, SVC-10 RAG Card Review, SVC-06 Source Registry, SVC-38 Artifact Storage.

### Информационный обмен

С `SVC-07` — parsed sections. С `SVC-08` — правила metadata. С `SVC-20` — prompt на генерацию. С `SVC-10` — драфты карточек. С `SVC-38` — сохранение `.md` файлов.

### Входные данные

Parsed section, source metadata, ontology, prompt template, card generation policy.

### Выходные данные

`RAGCardDTO`, draft RAG-card file, generation confidence, validation report, source links.

### Реализует фичи

[SETUP-05](../../02-system/features/SETUP-05-rag-cards-generation.md).

---

## SVC-10. RAG Card Review Service

### Назначение

Просмотр, редактирование, подтверждение и отклонение RAG-карточек (HITL).

### Функции

Отдаёт карточки во frontend, принимает решения, управляет статусами `draft → review_required → approved | rejected | regenerate_requested`.

### DTO

`RAGCardDTO`, `RAGMetadataDTO`, `ValidationReportDTO`, `AuditEventDTO`.

### Внешние участники

EXT-02 RAG admin, EXT-03 SME.

### Соседние сервисы

SVC-01 Frontend, SVC-02 API Gateway, SVC-09 RAG Card Generator, SVC-08 Metadata Validator, SVC-38 Artifact Storage, SVC-36 Audit.

### Информационный обмен

С `SVC-01` — карточки и решения. С `SVC-08` — ошибки metadata. С `SVC-09` — запрос на регенерацию. С `SVC-36` — review events.

### Входные данные

Draft RAG cards, user edits, approve/reject commands, validation errors.

### Выходные данные

Approved RAG cards, rejected cards, review history, новые версии карточек.

### Реализует фичи

[SETUP-06](../../02-system/features/SETUP-06-rag-card-review.md).

---

## SVC-11. Chunking Service

### Назначение

Логическое разбиение одобренных RAG-карточек на retrievable чанки.

### Функции

Делит карточки на `summary`, `definition`, `inputs/outputs`, `formula`, `validation`, `examples`, `agent_usage`. Формирует chunk metadata и `embedding_text`.

### DTO

`RAGCardDTO`, `ChunkDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-02 RAG admin (косвенно).

### Соседние сервисы

SVC-04 Setup Orchestrator, SVC-10 RAG Card Review, SVC-08 Ontology, SVC-12 Embedding, SVC-06 Source Registry, SVC-38 Artifact Storage.

### Информационный обмен

С `SVC-10` — approved cards. С `SVC-08` — проверка chunk metadata. С `SVC-12` — chunks для embedding. С `SVC-38` — `chunk_manifest.jsonl`.

### Входные данные

Approved RAG cards, chunking policy, metadata schema.

### Выходные данные

`ChunkDTO`, chunk manifest, chunk validation report, chunk statistics.

### Реализует фичи

[SETUP-08](../../02-system/features/SETUP-08-chunking.md).

---

## SVC-12. Embedding Service

### Назначение

Построение векторных представлений чанков.

### Функции

Принимает `embedding_text`, вызывает embedding model, создаёт embedding vector, сохраняет параметры модели и передаёт результат на индексацию.

### DTO

`ChunkDTO`, `EmbeddingDTO`, `VectorIndexDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-08 Embedding Model.

### Соседние сервисы

SVC-11 Chunking, SVC-13 Vector Indexer, SVC-04 Setup Orchestrator, наблюдательный сервис (Observability).

### Информационный обмен

С `SVC-11` — chunks. С `EXT-08` — текст ↔ embedding vector. С `SVC-13` — embeddings + metadata. С Observability — latency / error metrics.

### Входные данные

Chunk text, chunk metadata, embedding model name, batch size, index version.

### Выходные данные

`EmbeddingDTO`, embedding batch report, errors, latency metrics.

### Реализует фичи

[SETUP-09](../../02-system/features/SETUP-09-embeddings-index.md) (часть embedding).

---

## SVC-13. Vector Indexer Service

### Назначение

Индексирует embeddings и metadata в Vector DB.

### Функции

Создаёт collections, сохраняет vectors, chunk text, doc metadata, chunk metadata, поддерживает reindex и versioned indexes.

### DTO

`EmbeddingDTO`, `ChunkDTO`, `VectorIndexDTO`.

### Внешние участники

EXT-09 Vector DB, EXT-02 RAG admin.

### Соседние сервисы

SVC-12 Embedding, SVC-15 KB Registry, SVC-21 RAG Retrieval, SVC-04 Setup Orchestrator, SVC-35 Analytics.

### Информационный обмен

С `SVC-12` — embeddings. С `EXT-09` — vectors + metadata. С `SVC-15` — `index_version`. С `SVC-35` — indexing statistics.

### Входные данные

Embeddings, chunk metadata, collection names, index version.

### Выходные данные

Vector index, `VectorIndexDTO`, indexing report, collection statistics, failed chunk list.

### Реализует фичи

[SETUP-09](../../02-system/features/SETUP-09-embeddings-index.md) (часть индексации).

---

## SVC-14. Retrieval Evaluation Service

### Назначение

Проверка качества RAG-базы до публикации.

### Функции

Запускает контрольные queries, сравнивает с ожидаемыми doc_ids, считает recall@k, precision@k, no-context rate, формирует отчёт.

### DTO

`RetrievalQueryDTO`, `RetrievedChunkDTO`, `ValidationReportDTO`, `VectorIndexDTO`.

### Внешние участники

EXT-02 RAG admin, EXT-03 SME.

### Соседние сервисы

SVC-21 RAG Retrieval, SVC-13 Vector Indexer, SVC-15 KB Registry, SVC-04 Setup Orchestrator, SVC-01 Frontend, SVC-35 Analytics.

### Информационный обмен

С `SVC-21` — test queries. С `SVC-15` — candidate index version. С `SVC-04` — pass/fail status. С `SVC-01` — retrieval report.

### Входные данные

Eval dataset, expected doc ids, vector index version, retrieval policy.

### Выходные данные

Retrieval evaluation report, failed queries, score metrics, рекомендация publish/review.

### Реализует фичи

[SETUP-10](../../02-system/features/SETUP-10-retrieval-tests.md).

---

## SVC-15. Knowledge Base Registry

### Назначение

Управление версиями KB и статусом готовности RAG.

### Функции

Хранит KB-версии, связывает версии карточек, chunks и vector index, фиксирует активную версию и отдаёт её runtime-сервисам.

### DTO

`VectorIndexDTO`, `RAGCardDTO`, `ChunkDTO`, `KnowledgeBaseVersionDTO`, `AuditEventDTO`.

### Внешние участники

EXT-02 RAG admin, EXT-01 пользователь-настройщик.

### Соседние сервисы

SVC-04 Setup Orchestrator, SVC-13 Vector Indexer, SVC-21 RAG Retrieval, SVC-18 LangGraph Orchestrator, SVC-35 Analytics, SVC-36 Audit.

### Информационный обмен

С `SVC-04` — команда publish. С `SVC-21` — active KB version. С `SVC-18` — какая KB активна для runtime-сессии. С `SVC-36` — `kb_published`.

### Входные данные

Approved card versions, chunk manifest version, vector index version, retrieval test report, publish command.

### Выходные данные

Активная `knowledge_base_version`, status `ready`, version history, publish audit event.

### Реализует фичи

[SETUP-11](../../02-system/features/SETUP-11-publish-kb.md).

---

## Связанные документы

- [README.md](README.md)
- [../c4-component-rag-service.md](../c4-component-rag-service.md)
- [../c4-component-setup-orchestrator.md](../c4-component-setup-orchestrator.md)
- [../../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md](../../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md)
- [../../06-rag/rag-overview.md](../../06-rag/rag-overview.md)
