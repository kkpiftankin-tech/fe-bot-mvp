# План реализации SETUP-01. Пользовательский мастер настройки базы знаний

Нумерованный список задач, упорядоченных по зависимостям. Реализует фичу из [docs/02-system/features/SETUP-01-setup-wizard.md](../02-system/features/SETUP-01-setup-wizard.md). Каждая задача ссылается на docs, schemas, валидаторы и тесты.

Задачи сгруппированы в **9 вертикальных слайсов** (S0–S8), каждый из которых даёт работоспособное приращение функциональности. Слайсы можно реализовывать последовательно — следующий не требуется до завершения предыдущего, но допускает параллельную работу по командам Frontend / Backend / RAG.

## Логика слайсов

```text
S0. Фундамент: схемы и миграции             → 5 задач
S1. Skeleton API + Auth + Setup Job         → 6 задач
S2. Document upload + Source Registry       → 5 задач
S3. Parser + RAG Card Generator (с LLM)     → 7 задач
S4. Metadata Validation + Review            → 5 задач
S5. Chunking + Embedding + Vector Index     → 6 задач
S6. Retrieval Evaluation + KB Publish       → 5 задач
S7. Frontend wizard (полный мастер)         → 8 задач
S8. Observability, audit, traceability      → 4 задачи
```

Итого 51 задача (T-S01-001..T-S01-051) + 6 cross-cutting задач инфраструктуры (T-S01-INF-001..006).

---

## Cross-cutting инфраструктура

### T-S01-INF-001. Docker Compose профиль `setup`

Target:
- [infra/compose/docker-compose.yml](../../infra/compose/docker-compose.yml) (профиль `setup`)
- [README.md](../../README.md) (раздел запуска)

Acceptance:
- `make up-setup` поднимает PostgreSQL + MinIO + Qdrant + Ollama.
- Healthcheck-и проходят за < 60 c.
- Переменные окружения вынесены в `.env.example`.

### T-S01-INF-002. PostgreSQL миграции

Target:
- `migrations/setup/001_init_setup_schema.sql`
- `migrations/setup/002_rag_cards.sql`
- `migrations/setup/003_chunks_index_kb.sql`

Acceptance:
- Миграции применяются идемпотентно (`alembic upgrade head` дважды — no-op).
- Индексы из [SETUP-01 §11.2](../02-system/features/SETUP-01-setup-wizard.md#112-изменения-в-данных) присутствуют.
- Rollback-скрипты есть для каждой миграции.

### T-S01-INF-003. MinIO bucket layout

Target:
- `infra/minio/bootstrap.sh`
- `docs/03-architecture/services/storage-conventions.md` (раздел layouts)

Acceptance:
- Бакеты: `source-documents`, `rag-cards`, `chunk-manifests`, `processing-reports`.
- Lifecycle policy для `processing-reports` (TTL 90 дней).
- Per-setup-job-prefix: `s3://source-documents/{setup_job_id}/...`.

### T-S01-INF-004. Qdrant collections bootstrap

Target:
- `scripts/qdrant_init.py`
- `tests/integration/test_qdrant_bootstrap.py`

Acceptance:
- Создаёт 8 коллекций из [docs/06-rag/document-types.md](../06-rag/document-types.md) (по `doc_type`).
- Метаданные коллекций включают `embedding_model`, `dimension`, `kb_version`.
- Повторный запуск — no-op.

### T-S01-INF-005. Ollama bootstrap

Target:
- `infra/ollama/pull_models.sh`
- `docs/03-architecture/adr/ADR-002-ollama-default-llm.md` (модели по умолчанию)

Acceptance:
- `llama3.2` загружена.
- `nomic-embed-text` загружена (для embeddings).
- `make ollama-models` — идемпотентен.

### T-S01-INF-006. Makefile цели для Setup-пайплайна

Target:
- [Makefile](../../Makefile)
- [docs/06-rag/rag-quality.md §Команды разработки](../06-rag/rag-quality.md#команды-разработки)

Acceptance:
- `make rag-generate`, `rag-validate`, `rag-chunk`, `rag-embed`, `rag-index`, `rag-eval`, `rag-publish`, `rag-reindex` работают.
- Каждая цель идемпотентна.

---

## S0. Фундамент: схемы и миграции

### T-S01-001. RAGSetupJob schema (DTO-07)

Target:
- `schemas/setup/rag_setup_job.py`
- `tests/unit/test_rag_setup_job_schema.py`

Acceptance:
- Все поля из [DTO-07](../03-architecture/services/data-transfer-objects.md#dto-07-ragsetupjobdto).
- 15 статусов из [SETUP-01 §3](../02-system/features/SETUP-01-setup-wizard.md#статусы-setup-job) форсятся через enum.
- Невалидные переходы (`ready → parsing`) отвергаются методом `transition_to()`.
- `progress_percent` ∈ [0.0, 100.0].

### T-S01-002. SourceDocument + UploadFile schemas (DTO-08, DTO-09)

Target:
- `schemas/setup/source_document.py`
- `schemas/setup/upload_file.py`
- `tests/unit/test_source_document_schema.py`

Acceptance:
- Поля из [DTO-08](../03-architecture/services/data-transfer-objects.md#dto-08-uploadfiledto), [DTO-09](../03-architecture/services/data-transfer-objects.md#dto-09-sourcedocumentdto).
- `checksum` валидируется как SHA-256.
- `content_type` ∈ {md, txt, pdf, docx, xlsx, csv, json}.
- `size_bytes` ≤ `MAX_FILE_SIZE_BYTES` (env var).

### T-S01-003. ParsedSection, RAGCard, RAGMetadata schemas (DTO-10, DTO-11, DTO-12)

Target:
- `schemas/setup/parsed_section.py`
- `schemas/rag/rag_card.py`
- `schemas/rag/rag_metadata.py`
- `tests/unit/test_rag_card_schema.py`

Acceptance:
- Поля из [DTO-10/11/12](../03-architecture/services/data-transfer-objects.md#3-dto-настройки-rag-базы).
- `RAGMetadata.doc_type` ∈ онтологии ([docs/06-rag/document-types.md](../06-rag/document-types.md)).
- `RAGCard.status` использует машину состояний из [rag-lifecycle.md](../06-rag/rag-lifecycle.md).
- YAML-front-matter `RAGCard` сериализуется и парсится round-trip.

### T-S01-004. Chunk, Embedding, VectorIndex, KnowledgeBaseVersion schemas (DTO-14..17)

Target:
- `schemas/rag/chunk.py`
- `schemas/rag/embedding.py`
- `schemas/rag/vector_index.py`
- `schemas/rag/knowledge_base_version.py`
- `tests/unit/test_chunk_schema.py`
- `tests/unit/test_kb_version_schema.py`

Acceptance:
- `Chunk.chunk_type` ∈ {summary, definition, formula, validation, example, agent_usage}.
- `Embedding.dimension` совпадает с `embedding_model.dimension`.
- `KnowledgeBaseVersion` — иммутабельная Pydantic-модель после `status = active`.
- `VectorIndex.index_version` ↔ `KnowledgeBaseVersion.knowledge_base_version` 1:1.

### T-S01-005. RAG metadata validator (детерминированный)

Target:
- `validators/rag_metadata_validator.py`
- `tests/unit/test_rag_metadata_validator.py`

Acceptance:
- Все правила из [rag-quality.md §1.1](../06-rag/rag-quality.md#11-валидация-rag-карточек).
- Возвращает `ValidationReportDTO` (DTO-32) с `errors[]`, `warnings[]`, `repair_instruction`.
- Тест: 12 кейсов (валидная, отсутствие `doc_id`, неизвестный `doc_type`, не-онтологический `domain`, дубликат `doc_id`, …).
- Покрытие веток ≥ 90%.

---

## S1. Skeleton API + Auth + Setup Job

### T-S01-006. FastAPI router `setup`

Target:
- `src/fe_bot/api/setup/router.py`
- `tests/contract/test_setup_endpoints_openapi.py`

Acceptance:
- 12 endpoints из [SETUP-01 §16.1](../02-system/features/SETUP-01-setup-wizard.md#161-rest-api) зарегистрированы (skeleton-возвраты 501 пока не реализованы).
- OpenAPI snapshot сгенерирован и закоммичен.
- Версия API: `/api/v1/setup`.

### T-S01-007. Auth Service stub (SVC-03)

Target:
- `src/fe_bot/auth/service.py`
- `src/fe_bot/auth/permissions.py`
- `tests/unit/test_auth_permissions.py`

Acceptance:
- В MVP — header-based stub (`X-User-Id`, `X-Roles`); полноценный OIDC отложен.
- 6 permissions из [SETUP-01 §5.3](../02-system/features/SETUP-01-setup-wizard.md#53-права-доступа) проверяются.
- `403 Forbidden` возвращается при отсутствии permission.

### T-S01-008. Setup Orchestrator skeleton (SVC-04)

Target:
- `src/fe_bot/setup/orchestrator/state_machine.py`
- `src/fe_bot/setup/orchestrator/service.py`
- `tests/unit/test_setup_state_machine.py`

Acceptance:
- LangGraph state machine из 13 шагов (`upload → parse → ... → publish`).
- Каждый переход эмитит `SetupProgressEvent`.
- Состояние персистится в PostgreSQL (LangGraph checkpointer).
- Прерывание процесса — resumable из последнего checkpoint.

### T-S01-009. POST /setup/jobs

Target:
- `src/fe_bot/api/setup/create_job.py`
- `src/fe_bot/setup/orchestrator/create_job.py`
- `tests/integration/test_create_setup_job.py`

Acceptance:
- AC-01..AC-03 из [SETUP-01 §19](../02-system/features/SETUP-01-setup-wizard.md#создание-setup-job) проходят.
- Запись в `rag_setup_jobs` создаётся, статус = `draft`.
- Эмитится событие `setup.job.created` (для MVP — в PostgreSQL events-таблицу).
- Аудит-запись (DTO-48) пишется.

### T-S01-010. GET /setup/{id} и GET /setup/{id}/progress

Target:
- `src/fe_bot/api/setup/get_status.py`
- `tests/integration/test_get_setup_status.py`

Acceptance:
- Возвращает `RAGSetupJobResponse` из [SETUP-01 §15.2](../02-system/features/SETUP-01-setup-wizard.md#152-выходные-dto).
- Progress endpoint поддерживает long-polling (Server-Sent Events опционально, в MVP — polling каждые 2 с).
- 404 если `setup_job_id` не существует.
- 403 если пользователь не владелец и не имеет `kb.setup.create`.

### T-S01-011. POST /setup/{id}/cancel

Target:
- `src/fe_bot/api/setup/cancel_job.py`
- `tests/integration/test_cancel_setup_job.py`

Acceptance:
- Job переходит в `cancelled`.
- LangGraph checkpoint завершается gracefully (не оставляет orphan-таски).
- Уже созданные draft-артефакты помечаются `cancelled`.
- Аудит-запись.

---

## S2. Document upload + Source Registry

### T-S01-012. Document Upload Service (SVC-05)

Target:
- `src/fe_bot/setup/upload/service.py`
- `src/fe_bot/setup/upload/validation.py`
- `tests/unit/test_upload_validation.py`

Acceptance:
- Валидирует формат, размер, не-пустой контент.
- Считает `checksum` (SHA-256).
- Отвергает: `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `EMPTY_FILE` (см. [§18.1](../02-system/features/SETUP-01-setup-wizard.md#181-ошибки-валидации)).
- AC-04..AC-06 проходят.

### T-S01-013. POST /setup/{id}/documents

Target:
- `src/fe_bot/api/setup/upload_documents.py`
- `tests/integration/test_upload_documents.py`

Acceptance:
- Multipart upload работает.
- Файл сохраняется в MinIO по пути `{setup_job_id}/{source_document_id}/{filename}`.
- `SourceDocumentDTO` создаётся в `source_documents`.
- Идемпотентность: повторный upload того же checksum → `Duplicate document detected`, варианты `skip / replace / new version` (AC-07).

### T-S01-014. Source Registry Service (SVC-06)

Target:
- `src/fe_bot/setup/source_registry/service.py`
- `tests/unit/test_source_registry.py`

Acceptance:
- CRUD по `SourceDocumentDTO`.
- Дедупликация по `checksum` внутри `setup_job_id`.
- Метод `get_documents_for_job(setup_job_id)` возвращает в порядке загрузки.

### T-S01-015. GET /setup/{id}/documents

Target:
- `src/fe_bot/api/setup/list_documents.py`
- `tests/integration/test_list_documents.py`

Acceptance:
- Возвращает список `SourceDocumentDTO`.
- Пагинация (`limit`, `offset`) — необязательна в MVP, лимит 1000.
- Поле `download_url` — presigned URL MinIO с TTL 1 час.

### T-S01-016. Artifact Storage Service (SVC-38, MVP-минимум)

Target:
- `src/fe_bot/storage/artifact_service.py`
- `tests/integration/test_artifact_storage.py`

Acceptance:
- MinIO-клиент инкапсулирован.
- Методы: `upload`, `download`, `delete`, `presigned_url`, `checksum`.
- TTL на presigned URLs.
- При недоступности MinIO — `OBJECT_STORAGE_UNAVAILABLE` ([§18.2](../02-system/features/SETUP-01-setup-wizard.md#182-системные-ошибки)).

---

## S3. Parser + RAG Card Generator (с LLM)

### T-S01-017. Document Parser Service: Markdown (SVC-07, базовый формат)

Target:
- `src/fe_bot/setup/parser/markdown_parser.py`
- `tests/unit/test_markdown_parser.py`

Acceptance:
- Разбивает Markdown по заголовкам H1/H2/H3.
- Каждая секция → `ParsedSectionDTO` с `title`, `section_path[]`, `raw_text`, `normalized_text`.
- Поддержка YAML front matter (если есть).
- 5 тестовых документов из `tests/fixtures/markdown/`.

### T-S01-018. Document Parser Service: остальные форматы

Target:
- `src/fe_bot/setup/parser/pdf_parser.py` (pypdf или pdfminer)
- `src/fe_bot/setup/parser/docx_parser.py` (python-docx)
- `src/fe_bot/setup/parser/xlsx_parser.py` (openpyxl)
- `src/fe_bot/setup/parser/csv_json_parser.py`
- `tests/unit/test_parsers.py`

Acceptance:
- Для каждого формата — успешный happy-path тест на фикстуре.
- Failed parse → `SourceDocumentDTO.status = failed` и `error_message` (см. N4).
- OCR **не** реализуется (out of scope).

### T-S01-019. LLM Gateway (SVC-20, минимум для card generation)

Target:
- `src/fe_bot/llm_gateway/client.py`
- `src/fe_bot/llm_gateway/structured_output.py`
- `tests/unit/test_llm_gateway.py` (с замоканным Ollama)
- `tests/integration/test_llm_gateway_ollama.py` (требует профиль `llm`)

Acceptance:
- Унифицированный клиент к Ollama (`/api/generate`, `/api/embeddings`).
- Structured output: повторный вызов при невалидном JSON (max 2 retry — [§16.3](../02-system/features/SETUP-01-setup-wizard.md#163-контрактные-требования)).
- При недоступности — `LLM_UNAVAILABLE`.
- Логирует `prompt_id`, `model`, `latency_ms`, `tokens` (DTO-25, DTO-26).

### T-S01-020. RAG Card Generator (SVC-09)

Target:
- `src/fe_bot/setup/card_generator/service.py`
- `prompts/rag_card_generator.md`
- `tests/component/test_rag_card_generator.py` (LLM моки)

Acceptance:
- На входе — `ParsedSectionDTO`, на выходе — `RAGCardDTO` (draft).
- Промпт включает: тип секции → ожидаемый `doc_type`, ontology slots, требуемая metadata.
- Detection эвристика: section_type → preferred `doc_type` (schema_card / task_card / analytics_card / …).
- Confidence score ≥ 0.7 для approve без HITL, иначе `review_required`.
- Тесты: 8 кейсов (разные `doc_type`, low-confidence, ошибка LLM, повторная генерация).

### T-S01-021. RAG Card Fallback Generator (без LLM)

Target:
- `src/fe_bot/setup/card_generator/fallback.py`
- `tests/unit/test_fallback_generator.py`

Acceptance:
- Включается при `LLM_UNAVAILABLE` или env-флаге `RAG_CARD_FALLBACK=true`.
- Генерирует карточки по шаблонам с пометкой `confidence_level = low` и `status = review_required`.
- Все карточки требуют HITL.

### T-S01-022. POST /setup/{id}/run

Target:
- `src/fe_bot/api/setup/run_pipeline.py`
- `tests/integration/test_run_pipeline.py`

Acceptance:
- Запускает Setup Orchestrator асинхронно.
- Поддерживает `run_mode = full | resume`, `start_from_step`, `force_regenerate_cards`, `force_reindex` (см. A4).
- Возвращает 202 Accepted с `setup_job_id`.
- При повторном вызове на job в статусе `running` → 409 Conflict.

### T-S01-023. Setup Orchestrator: интеграция parser + card generator

Target:
- `src/fe_bot/setup/orchestrator/steps/parse_step.py`
- `src/fe_bot/setup/orchestrator/steps/generate_cards_step.py`
- `tests/integration/test_orchestrator_parse_and_generate.py`

Acceptance:
- Step `parsing`: для каждого SourceDocument вызывает Parser, сохраняет ParsedSections.
- Step `rag_cards_generating`: для каждой ParsedSection вызывает RAG Card Generator.
- Прогресс эмитится после каждого документа (`SetupProgressEvent.progress_percent`).
- AC-08..AC-11 проходят.

---

## S4. Metadata Validation + Review

### T-S01-024. Metadata Validation Service (SVC-08)

Target:
- `src/fe_bot/setup/metadata_validation/service.py`
- `tests/integration/test_metadata_validation_service.py`

Acceptance:
- Обёртка над `validators/rag_metadata_validator.py` (T-S01-005).
- Возвращает `ValidationReportDTO` (DTO-32) с `target_type=rag_card`.
- Карточки с errors → `failed`; с warnings → `review_required`; без проблем → `metadata_validated`.
- AC-14 проходит.

### T-S01-025. RAG Card Review Service (SVC-10)

Target:
- `src/fe_bot/setup/card_review/service.py`
- `src/fe_bot/setup/card_review/decision_log.py`
- `tests/unit/test_card_review_service.py`

Acceptance:
- 4 действия: `approve`, `reject`, `edit`, `regenerate` (см. A2, AC-15).
- Каждое действие → `RAGCardReviewDTO` (DTO-13) с before/after версией.
- `edit` создаёт новую версию карточки (vN+1), старая → `deprecated`.
- `regenerate` ставит карточку обратно в очередь Card Generator.

### T-S01-026. POST /setup/{id}/rag-cards/{doc_id}/review

Target:
- `src/fe_bot/api/setup/review_card.py`
- `tests/integration/test_review_card_endpoint.py`

Acceptance:
- Принимает `ReviewRAGCardRequest`.
- Permission: `kb.card.review`.
- Аудит-запись (DTO-48).
- При `regenerate` Setup Orchestrator перепоставляет шаг.

### T-S01-027. GET /setup/{id}/rag-cards

Target:
- `src/fe_bot/api/setup/list_cards.py`
- `tests/integration/test_list_cards.py`

Acceptance:
- Фильтры: `status`, `doc_type`, `confidence_level`.
- Возвращает YAML front matter + укороченный body (≤ 500 символов) или полный body по `?include=body`.
- Сортировка: review_required → metadata_validated → approved → published.

### T-S01-028. Step: metadata_validating + review_required

Target:
- `src/fe_bot/setup/orchestrator/steps/validate_metadata_step.py`
- `src/fe_bot/setup/orchestrator/steps/review_gate_step.py`
- `tests/integration/test_orchestrator_validation_and_review.py`

Acceptance:
- Step ждёт завершения review всех `review_required` карточек.
- Если `review_policy = strict` — pipeline ждёт; если `allow_warnings` — пропускает warning, ждёт errors (см. [§12](../02-system/features/SETUP-01-setup-wizard.md#бизнес-правила-и-ограничения)).
- Setup job статус: `review_required` или `metadata_validated`.

---

## S5. Chunking + Embedding + Vector Index

### T-S01-029. Chunking Service (SVC-11)

Target:
- `src/fe_bot/setup/chunking/service.py`
- `src/fe_bot/setup/chunking/strategies.py`
- `tests/unit/test_chunking_strategies.py`

Acceptance:
- Стратегии: `summary`, `definition`, `formula`, `validation`, `example` ([chunk-schema.md](../06-rag/chunk-schema.md)).
- `embedding_text` ≤ 1024 токенов.
- `chunk_id = "{doc_id}#{slot}#{n}"` — детерминированный, идемпотентный (INV-ID-003).
- `chunk_manifest.jsonl` сохраняется в MinIO.
- AC-16, AC-17 проходят.

### T-S01-030. Embedding Service (SVC-12)

Target:
- `src/fe_bot/setup/embedding/service.py`
- `tests/integration/test_embedding_service.py` (требует Ollama)

Acceptance:
- Batch размером ≥ 32.
- Использует `nomic-embed-text` через LLM Gateway по умолчанию.
- Retry с backoff при `EMBEDDING_MODEL_UNAVAILABLE`.
- `Embedding.dimension` сохраняется в `VectorIndex`.
- AC-18 проходит.

### T-S01-031. Vector DB Indexer (SVC-13)

Target:
- `src/fe_bot/setup/vector_indexer/service.py`
- `src/fe_bot/setup/vector_indexer/qdrant_client.py`
- `tests/integration/test_vector_indexer.py` (требует Qdrant)

Acceptance:
- Upsert chunks в коллекцию по `doc_type` (см. T-S01-INF-004).
- Идемпотентный upsert: повторный вызов на тех же `chunk_id` — no-op.
- `VectorIndexDTO` (DTO-16) создаётся с `status=building` → `ready`.
- AC-19, AC-20 проходят.

### T-S01-032. Steps: chunking → embedding → indexing

Target:
- `src/fe_bot/setup/orchestrator/steps/chunking_step.py`
- `src/fe_bot/setup/orchestrator/steps/embedding_step.py`
- `src/fe_bot/setup/orchestrator/steps/indexing_step.py`
- `tests/integration/test_orchestrator_indexing_pipeline.py`

Acceptance:
- Steps вызываются последовательно.
- На каждом failed step pipeline останавливается, статус = `failed`, артефакты предыдущих шагов **не удаляются** (compensation [§18.3](../02-system/features/SETUP-01-setup-wizard.md#183-поведение-системы)).
- `force_reindex=true` начинает заново с chunking.

### T-S01-033. Резистентность embedding+indexing

Target:
- `tests/integration/test_embedding_failure_recovery.py`
- `tests/integration/test_indexing_failure_recovery.py`

Acceptance:
- Имитация: Ollama падает после половины batch'ей → retry, потом продолжение.
- Имитация: Qdrant возвращает 5xx → retry с backoff, потом `INDEXING_FAILED`.
- В обоих случаях `RAGSetupJob.status = failed`, KB не публикуется.

### T-S01-034. POST /setup/{id}/reindex

Target:
- `src/fe_bot/api/setup/reindex.py`
- `tests/integration/test_reindex_endpoint.py`

Acceptance:
- Создаёт новую `index_version` без затрагивания текущей `active KB`.
- Permission: `kb.publish` (потому что reindex может сменить active KB).
- Поддерживает `from_step` (chunking / embedding / indexing).

---

## S6. Retrieval Evaluation + KB Publish

### T-S01-035. Golden retrieval test dataset

Target:
- `rag/eval/rag_eval_dataset.yaml`
- `tests/unit/test_eval_dataset_schema.py`

Acceptance:
- ≥ 10 кейсов из [rag-quality.md §2.2](../06-rag/rag-quality.md#22-golden-dataset).
- Схема `RetrievalEvaluationCaseDTO` (DTO-21).
- Профили: `basic` (5 кейсов), `domain` (15 кейсов), `custom` (определяется пользователем).

### T-S01-036. Retrieval Evaluation Service (SVC-14)

Target:
- `src/fe_bot/setup/eval/service.py`
- `src/fe_bot/setup/eval/metrics.py`
- `tests/unit/test_eval_metrics.py`
- `tests/integration/test_eval_service.py`

Acceptance:
- Метрики из [rag-quality.md §2.1](../06-rag/rag-quality.md#21-offline-evaluation-после-индексации): `recall@5`, `precision@5`, `MRR`, `no_context_rate`.
- Возвращает `RetrievalEvaluationReportDTO` (DTO-22).
- Пороги читаются из `rag/eval/thresholds.yaml`, дефолты: recall@5 ≥ 0.85, no_context_rate ≤ 0.05.
- AC-21, AC-22 проходят.

### T-S01-037. Knowledge Base Registry (SVC-15)

Target:
- `src/fe_bot/setup/kb_registry/service.py`
- `tests/integration/test_kb_registry.py`

Acceptance:
- Публикация = атомарный переход `status: ready → active` + деактивация старой активной KB (если есть).
- Поддерживает одну active KB на проект (MVP-ограничение).
- Иммутабельность: после `active` карточки не меняются, только новая версия.
- AC-23, AC-24 проходят.

### T-S01-038. POST /setup/{id}/publish + step `publishing`

Target:
- `src/fe_bot/api/setup/publish.py`
- `src/fe_bot/setup/orchestrator/steps/publish_step.py`
- `tests/integration/test_publish_kb.py`

Acceptance:
- Permission: `kb.publish`.
- Запрещает публикацию без `vector_index_ready` и `retrieval_tests_passed` (бизнес-правило [§12](../02-system/features/SETUP-01-setup-wizard.md#правила-принятия-решений)).
- `allow_warnings=true` — только для `rag_admin`.
- Эмитит `setup.kb.ready`, аудит-запись.
- AC-25, AC-29 проходят.

### T-S01-039. Processing Report (DTO-51) + GET /setup/{id}/report

Target:
- `src/fe_bot/setup/report/service.py`
- `src/fe_bot/api/setup/get_report.py`
- `tests/integration/test_processing_report.py`

Acceptance:
- Report содержит: `steps[]` с длительностями, `errors[]`, `warnings[]`, `metrics{}`.
- Сохраняется в MinIO как `processing-reports/{setup_job_id}/report.json`.
- Доступен по presigned URL.
- AC-26, AC-27 проходят.

---

## S7. Frontend wizard

> Все frontend-задачи требуют завершённого S1; S2/S3 могут вестись параллельно с S7-задачами в качестве моков.

### T-S01-040. Skeleton Knowledge Base Setup Page

Target:
- `frontend/src/pages/SetupWizard/index.tsx`
- `frontend/src/api/setup.ts` (typed клиент к API)
- `frontend/tests/e2e/setup-wizard-skeleton.spec.ts` (Playwright)

Acceptance:
- Маршрут `/setup` рендерится для авторизованных.
- Шаги мастера (Mantine `Stepper` / shadcn): Upload → Process → Review → Publish.
- Заглушки страниц переключаются по `setup_job.status`.

### T-S01-041. FileUploadPanel + UploadedFilesTable

Target:
- `frontend/src/components/setup/FileUploadPanel.tsx`
- `frontend/src/components/setup/UploadedFilesTable.tsx`
- `frontend/tests/component/FileUploadPanel.test.tsx`

Acceptance:
- Drag-and-drop + диалог.
- Client-side валидация: формат, размер ≤ env-конфиг, дедупликация в рамках сессии.
- Список файлов с колонками из [§10.1](../02-system/features/SETUP-01-setup-wizard.md#101-ui-компоненты).
- Inline errors для каждого файла.

### T-S01-042. SetupProgressTimeline + ProcessingStatusPanel

Target:
- `frontend/src/components/setup/SetupProgressTimeline.tsx`
- `frontend/src/components/setup/ProcessingStatusPanel.tsx`
- `frontend/src/hooks/useSetupProgress.ts` (polling 2с)

Acceptance:
- 12 этапов с индикацией: pending / running / completed / failed.
- На failed этапе — actionable error + кнопка Retry.
- Auto-refresh при `setup_job.status ∈ {running}`.

### T-S01-043. RAGCardReviewPanel

Target:
- `frontend/src/components/setup/RAGCardReviewPanel.tsx`
- `frontend/src/components/setup/RAGCardDetailDrawer.tsx`
- `frontend/tests/component/RAGCardReviewPanel.test.tsx`

Acceptance:
- Список карточек с фильтрами (`doc_type`, `status`, `confidence`).
- Preview YAML front matter + Markdown body.
- 4 действия (approve / reject / edit / regenerate) — кнопки.
- При `edit` открывается редактор YAML + Markdown (если feature flag `enable_manual_card_edit`).

### T-S01-044. RetrievalSmokeTestReportPanel

Target:
- `frontend/src/components/setup/RetrievalSmokeTestReportPanel.tsx`
- `frontend/tests/component/RetrievalSmokeTestReportPanel.test.tsx`

Acceptance:
- Таблица: запрос → ожидаемые doc_ids → найденные → recall@5 → статус.
- Failed cases выделены красным с возможностью «открыть карточку».

### T-S01-045. PublishKnowledgeBasePanel + KnowledgeBaseReadyBanner

Target:
- `frontend/src/components/setup/PublishKnowledgeBasePanel.tsx`
- `frontend/src/components/setup/KnowledgeBaseReadyBanner.tsx`
- `frontend/tests/component/PublishPanel.test.tsx`

Acceptance:
- Кнопка Publish неактивна, пока `retrieval_test_status ≠ passed` (или `allow_warnings` + role=rag_admin).
- Подтверждающий диалог (dangerous action).
- Ready banner показывает 7 метрик из [§10.1 KnowledgeBaseReadyBanner](../02-system/features/SETUP-01-setup-wizard.md#knowledgebasereadybanner).

### T-S01-046. State management + restoration

Target:
- `frontend/src/store/setupStore.ts` (Zustand / Redux Toolkit)
- `frontend/tests/unit/setupStore.test.ts`

Acceptance:
- Состояние: setup_job, uploaded_files, progress, review, publish, errors.
- При reload страницы — восстановление по `setup_job_id` из URL (или localStorage).
- При закрытии браузера job продолжает работать на backend ([§17 Доступность](../02-system/features/SETUP-01-setup-wizard.md#доступность)).

### T-S01-047. E2E happy path (Playwright)

Target:
- `frontend/tests/e2e/setup-wizard-happy-path.spec.ts`
- `tests/e2e/test_setup_wizard_happy_path.py` (Python-обвязка для CI)

Acceptance:
- 10 шагов из [§21.4](../02-system/features/SETUP-01-setup-wizard.md#214-end-to-end--ui-tests).
- Прогон против локального docker-compose (профиль `setup`).
- Время выполнения ≤ 15 минут.
- Артефакты: video, trace, screenshot на failed.

---

## S8. Observability, audit, traceability

### T-S01-048. Audit Service (SVC-36, MVP-минимум)

Target:
- `src/fe_bot/audit/service.py`
- `tests/integration/test_audit_service.py`

Acceptance:
- `AuditEventDTO` (DTO-48) пишется в PostgreSQL events-таблицу.
- 6 типов событий из [§14.2 SETUP-01](../02-system/features/SETUP-01-setup-wizard.md#142-побочные-эффекты).
- AC-28 проходит.

### T-S01-049. Метрики + дашборд

Target:
- `src/fe_bot/observability/metrics.py`
- `docs/11-operations/metrics.md` (раздел Setup)
- `tests/unit/test_metrics_exposition.py`

Acceptance:
- 8 метрик из [§17 SETUP-01](../02-system/features/SETUP-01-setup-wizard.md#наблюдаемость).
- Prometheus-формат `/metrics` или OpenTelemetry.
- Grafana dashboard `setup-pipeline.json` (опционально для MVP).

### T-S01-050. Notification Service (SVC-37, MVP-минимум)

Target:
- `src/fe_bot/notification/service.py`
- `src/fe_bot/notification/sse_handler.py`
- `tests/integration/test_notification_sse.py`

Acceptance:
- `NotificationDTO` (DTO-50) доставляется через SSE на `/api/setup/{id}/events`.
- Channel = `sse` (MVP), email/websocket — отложены.
- 4 типа уведомлений: upload completed, review required, retrieval tests failed, KB ready.

### T-S01-051. Traceability обновления

Target:
- `docs/traceability/feature-to-service-map.md`
- `docs/traceability/dto-to-service-map.md`
- `docs/traceability/coverage-matrix.md`
- `docs/traceability/requirements-to-tests.md`

Acceptance:
- SETUP-01 → 20 SVC уже зафиксировано; проверить что список совпадает с реализованным.
- DTO-07..17, 22, 32, 48..51 → producer/consumer обновлены под реальные модули.
- Coverage matrix: SETUP-01 = `covered` после прохождения всех AC и зелёного E2E.
- `requirements-to-tests.md`: для AC-01..AC-29 указаны конкретные тестовые файлы.

---

## Тестовая стратегия по уровням

### Уровень 1: Unit tests (`tests/unit/`)

Покрытие: Pydantic-схемы, валидаторы, чистые функции.

| Слайс | Тесты |
| --- | --- |
| S0 | T-S01-001..005 — 5 schema/validator-тестов |
| S1 | test_auth_permissions, test_setup_state_machine |
| S2 | test_upload_validation, test_source_registry |
| S3 | test_markdown_parser, test_parsers, test_llm_gateway, test_fallback_generator |
| S4 | test_card_review_service |
| S5 | test_chunking_strategies |
| S6 | test_eval_metrics, test_eval_dataset_schema |
| S7 | setupStore.test.ts |
| S8 | test_metrics_exposition |

**Цель покрытия:** ≥ 85% по строкам, ≥ 90% по веткам в `validators/` и `schemas/`.

### Уровень 2: Component tests (`tests/component/`)

Покрытие: один сервис целиком + замоканные соседи (LLM, Qdrant, MinIO моки).

| Сервис | Тест |
| --- | --- |
| RAG Card Generator (SVC-09) | `test_rag_card_generator.py` — 8 кейсов |
| RAG Card Review Service (SVC-10) | `test_card_review_service.py` — переходы статусов |
| Frontend RAGCardReviewPanel | `RAGCardReviewPanel.test.tsx` (Vitest + Testing Library) |
| Frontend FileUploadPanel | `FileUploadPanel.test.tsx` |
| Frontend PublishPanel | `PublishPanel.test.tsx` |

### Уровень 3: Integration tests (`tests/integration/`)

Покрытие: реальный PostgreSQL + MinIO + (опционально) Qdrant + Ollama.

| Категория | Тесты |
| --- | --- |
| API endpoints | test_create_setup_job, test_upload_documents, test_run_pipeline, test_review_card_endpoint, test_list_cards, test_publish_kb, test_processing_report, test_cancel_setup_job, test_reindex_endpoint, test_get_setup_status, test_list_documents |
| Orchestrator | test_orchestrator_parse_and_generate, test_orchestrator_validation_and_review, test_orchestrator_indexing_pipeline |
| Services | test_artifact_storage, test_metadata_validation_service, test_embedding_service, test_vector_indexer, test_qdrant_bootstrap, test_kb_registry, test_eval_service |
| Resilience | test_embedding_failure_recovery, test_indexing_failure_recovery |

**Запуск:** `pytest tests/integration/ -m "integration"` после `make up-setup`.

### Уровень 4: Contract tests (`tests/contract/`)

Покрытие: OpenAPI / event schemas.

| Тест | Назначение |
| --- | --- |
| `test_setup_endpoints_openapi.py` | Snapshot-тест OpenAPI: detect breaking changes |
| `test_setup_events_schemas.py` | JSON Schema для 8 типов событий |
| `test_dto_backward_compat.py` | Старые клиенты не ломаются на новых ответах |

**Стратегия:** snapshot-тесты с явным `pytest --snapshot-update` при намеренных изменениях.

### Уровень 5: End-to-end tests (`tests/e2e/`)

Покрытие: реальный стек, реальный browser, happy path и ключевые альтернативы.

| Тест | Сценарий |
| --- | --- |
| `test_setup_wizard_happy_path.py` | Полный happy path (AC-01..AC-29) |
| `setup-wizard-happy-path.spec.ts` | Playwright equivalent |
| `setup-wizard-review-required.spec.ts` | A2: review required, approve, publish |
| `setup-wizard-retrieval-failed.spec.ts` | A3: retrieval tests partially failed, fix and rerun |

**Запуск в CI:** только на main и pre-merge для PR с меткой `setup-pipeline`.

### Уровень 6: Negative / resilience tests

Покрытие: failure modes из [§7.3](../02-system/features/SETUP-01-setup-wizard.md#73-негативные-сценарии) и [§18.2](../02-system/features/SETUP-01-setup-wizard.md#182-системные-ошибки).

| Тест | Сценарий |
| --- | --- |
| `test_upload_negative.py` | N1, N2, N3 (file type / size / duplicate) |
| `test_parse_failure.py` | N4 (битый PDF) |
| `test_llm_unavailable.py` | N5 (Ollama down) |
| `test_embedding_unavailable.py` | N6 |
| `test_vector_db_unavailable.py` | N7 |
| `test_permissions.py` | N8 (no kb.publish) |

### Уровень 7: Performance / load (post-MVP)

Не реализуется в SETUP-01, но фиксируется как баклог:

- Setup pipeline под нагрузкой (10 параллельных setup jobs).
- Время от upload до ready на корпусе 100 документов (≥ 1 MB каждый).
- Memory profiling embedding batch ≥ 1000 chunks.

---

## Зависимости между слайсами

```text
S0 (schemas)
  ├── S1 (skeleton API)
  │     └── S2 (upload)
  │           └── S3 (parser + LLM)
  │                 └── S4 (validation + review)
  │                       └── S5 (chunking + embedding + index)
  │                             └── S6 (eval + publish)
  │
  └── S8 (audit + observability + traceability)  — может идти параллельно с S2..S6

S7 (frontend) — может стартовать после S1; нужны моки S2/S3 пока бэкенд не готов.
```

**Критический путь:** S0 → S1 → S2 → S3 → S4 → S5 → S6 (последовательно).

**Параллелизация:**

- Frontend (S7) может вестись с момента готовности S1 — использует моки.
- Observability (S8) — параллельно с любым слайсом ≥ S1.
- Cross-cutting INF задачи (T-S01-INF-001..006) — до старта или в первые дни S0.

---

## Acceptance gates

Каждый слайс готов, когда:

| Slice | Gate |
| --- | --- |
| S0 | Все unit-тесты `tests/unit/test_*_schema.py` зелёные; `mypy schemas/` без ошибок |
| S1 | `curl POST /api/v1/setup/jobs` возвращает 200 со скелетным `setup_job_id`; OpenAPI snapshot закоммичен |
| S2 | Загрузка 3 файлов через API → видны в PostgreSQL и MinIO; AC-04..AC-07 проходят |
| S3 | `POST /run` → pipeline доходит до `metadata_validating` на тестовом корпусе; AC-08..AC-13 |
| S4 | Cards с low confidence → `review_required`; approve через API → переход в `chunking`; AC-14, AC-15 |
| S5 | После `indexing` Qdrant содержит ≥ 1 chunk; AC-16..AC-20 |
| S6 | E2E happy path до `ready`; AC-21..AC-25 |
| S7 | Playwright E2E зелёный; UI покрывает все 14 компонентов |
| S8 | AC-26..AC-29; traceability матрицы обновлены; coverage matrix = `covered` |

---

## Открытые вопросы (из SETUP-01 §22.3), которые блокируют конкретные задачи

| Вопрос | Блокирует задачу | Решение нужно к концу |
| --- | --- | --- |
| Максимальный размер файла? | T-S01-002, T-S01-012 | S2 |
| Какие embedding-модели в MVP? | T-S01-030, T-S01-INF-005 | S5 |
| Можно ли publish с warning? | T-S01-038 | S6 |
| OCR для PDF в MVP? | T-S01-018 | S3 |
| Карточки в Git или MinIO? | T-S01-020, T-S01-INF-003 | S3 |
| Multiple active KB на проект? | T-S01-037 | S6 |
| Минимальный retrieval pass rate? | T-S01-036, T-S01-038 | S6 |

**Действие:** до старта соответствующего слайса Product Owner / Architect фиксирует ответ в ADR или в виде обновления [SETUP-01 §22.3](../02-system/features/SETUP-01-setup-wizard.md#223-открытые-вопросы).

---

## Definition of Done всей фичи SETUP-01

```text
- 51 задача T-S01-001..051 закрыта.
- 6 cross-cutting INF задач закрыты.
- 29 acceptance criteria (AC-01..AC-29) проходят автотестом.
- E2E happy path зелёный в CI.
- Coverage: tests/unit ≥ 85%, tests/integration все green.
- OpenAPI snapshot закоммичен.
- Traceability матрицы обновлены.
- Все 7 открытых вопросов закрыты ADR-ами или обновлением §22.3.
- Product Owner принял demo на эталонном radar-корпусе.
- docs/02-system/features/SETUP-01-setup-wizard.md помечен Status: covered.
```

## Связанные документы

- [docs/02-system/features/SETUP-01-setup-wizard.md](../02-system/features/SETUP-01-setup-wizard.md)
- [docs/06-rag/rag-methodology.md](../06-rag/rag-methodology.md)
- [docs/06-rag/rag-lifecycle.md](../06-rag/rag-lifecycle.md)
- [docs/06-rag/rag-quality.md](../06-rag/rag-quality.md)
- [docs/03-architecture/services/data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md)
- [docs/03-architecture/services/setup-services.md](../03-architecture/services/setup-services.md)
- [docs/03-architecture/services/storage-conventions.md](../03-architecture/services/storage-conventions.md)
- [docs/00-methodology/development-process.md](../00-methodology/development-process.md)
- [docs/10-testing/testing-strategy.md](../10-testing/testing-strategy.md)
- [docs/implementation-plan/FE-BOT-MVP.tasks.md](FE-BOT-MVP.tasks.md)
