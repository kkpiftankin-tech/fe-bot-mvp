# SETUP-03 — Source Registry implementation plan

**Source feature spec:** [docs/02-system/features/SETUP-03-source-registry.md](../02-system/features/SETUP-03-source-registry.md) + приложенное детальное описание (23 секции, 34 AC, 7 endpoints).

**Цель:** превратить in-memory SourceRegistry из SETUP-02 в полноценный реестр источников с status history, processing log, lineage, downstream integration и UI.

**Scope-решения (закреплены 2026-06-10):**
- `/sources` URL prefix для новых endpoints (SETUP-02 `/documents` остаётся для upload-flow)
- PostgreSQL и Kafka отложены в INF-002 / INF-005 — всё in-memory, как в SETUP-01/02
- T-S02-016 retry endpoint реализуется здесь в S5
- Frontend SourceRegistryTab включён в S6 (полный MVP)
- Backend events публикуются через EventBus (как в SETUP-01 SetupProgressEvent), не Kafka

**Total tasks:** 29 в 8 вертикальных слайсах.

---

## S0. Schemas + DTOs (foundation)

### T-S03-001. Расширение SourceDocumentStatus enum

Target:
- `schemas/setup/source_document.py`
- `tests/unit/test_source_document_schema.py`

Добавить новые статусы (см. §3 спека):
- `REGISTERED = "registered"` — запись создана в Source Registry
- `METADATA_EXTRACTED = "metadata_extracted"` — metadata извлечена/обогащена
- `WAITING_FOR_PARSING = "waiting_for_parsing"`
- `PARSING = "parsing"`
- `PARSE_FAILED = "parse_failed"`
- `SECTIONS_EXTRACTED = "sections_extracted"`
- `RAG_CARDS_GENERATING = "rag_cards_generating"`
- `RAG_CARDS_GENERATED = "rag_cards_generated"`
- `REVIEW_REQUIRED = "review_required"`
- `PROCESSING_FAILED = "processing_failed"`
- `READY_FOR_INDEXING = "ready_for_indexing"`
- `PUBLISHED = "published"`
- `DEPRECATED = "deprecated"`

Сохранить существующие `UPLOADED`, `PARSED`, `CONVERTED`, `FAILED`, `FAILED_VALIDATION`, `ARCHIVED`, `REMOVED` для обратной совместимости.

Acceptance:
- Все 21 значение enum определены
- Существующие тесты SETUP-02 продолжают проходить
- Новые тесты проверяют наличие всех 13 новых значений

### T-S03-002. SourceDocumentStatusHistory DTO

Target:
- `schemas/setup/status_history.py`
- `tests/unit/test_status_history_schema.py`

Pydantic-схема:
```python
class SourceStatusHistoryEntry(BaseModel):
    status_history_id: str  # hist_xxx
    source_document_id: str
    old_status: SourceDocumentStatus | None  # None для initial
    new_status: SourceDocumentStatus
    reason: str | None
    event_id: str  # для idempotency
    changed_by_type: Literal["service", "user", "system"]
    changed_by_id: str
    changed_at: datetime
    metadata: dict[str, Any] = {}
```

+ state machine `ALLOWED_TRANSITIONS: dict[Status, set[Status]]` (см. §12 спека: нельзя REMOVED → PARSING, нельзя в PUBLISHED без lineage с KB version и т.д.).

Acceptance:
- DTO с extra="forbid" и валидацией
- `validate_transition(old, new) -> bool` функция
- 8+ allowed transitions покрыты тестами
- 5+ запрещённых transitions падают

### T-S03-003. SourceDocumentProcessingLog DTO

Target:
- `schemas/setup/processing_log.py`
- `tests/unit/test_processing_log_schema.py`

Pydantic-схема:
```python
class ProcessingLogLevel(StrEnum):
    DEBUG, INFO, WARNING, ERROR

class ProcessingLogStep(StrEnum):
    UPLOAD, REGISTRATION, METADATA_EXTRACTION, PARSING, SECTION_EXTRACTION,
    RAG_CARD_GENERATION, CHUNKING, EMBEDDING, INDEXING, REVIEW, PUBLISH

class SourceProcessingLogEntry(BaseModel):
    processing_log_id: str  # log_xxx
    source_document_id: str
    setup_job_id: str
    step: ProcessingLogStep
    level: ProcessingLogLevel
    message: str
    error_code: str | None
    event_id: str  # idempotency
    created_at: datetime
    payload: dict[str, Any] = {}
```

Acceptance:
- DTO с extra="forbid"
- Enums (10 steps, 4 levels) покрыты тестами
- Сериализация/десериализация corner cases

### T-S03-004. SourceDocumentLineage DTO + relation types

Target:
- `schemas/setup/lineage.py`
- `tests/unit/test_lineage_schema.py`

```python
class LineageTargetType(StrEnum):
    PARSED_SECTION = "parsed_section"
    RAG_CARD = "rag_card"
    CHUNK = "chunk"
    PROCESSING_REPORT = "processing_report"
    KNOWLEDGE_BASE_VERSION = "knowledge_base_version"

class LineageRelationType(StrEnum):
    PARSED_FROM = "parsed_from"
    GENERATED_FROM = "generated_from"
    DERIVED_FROM = "derived_from"
    INCLUDED_IN = "included_in"

class SourceLineageRelation(BaseModel):
    lineage_id: str
    source_document_id: str
    target_type: LineageTargetType
    target_id: str
    relation_type: LineageRelationType
    created_by_service: str
    created_at: datetime
    metadata: dict[str, Any] = {}

class SourceLineageSummary(BaseModel):
    source_document_id: str
    relations: list[SourceLineageRelation]
    counters: dict[str, int]  # parsed_sections_count, rag_cards_count, etc.
```

Acceptance:
- Unique constraint (source_document_id, target_type, target_id, relation_type)
- Counters сериализация
- 5 targets × 4 relations покрыты тестами

### T-S03-005. SourceDocumentUserMetadata DTO

Target:
- `schemas/setup/source_document_metadata.py`
- `tests/unit/test_user_metadata_schema.py`

```python
class SourceDocumentUserMetadata(BaseModel):
    tags: list[str] = []  # max 20, each ≤ 50 chars
    description: str | None = None  # ≤ 2000 chars
    owner_note: str | None = None  # ≤ 500 chars
    custom_labels: dict[str, str] = {}  # max 10 keys
```

Также `UpdateSourceMetadataRequest` с теми же ограничениями + sanitization (XSS).

Acceptance:
- Длина полей валидируется
- Pydantic строгий (extra="forbid")
- HTML/script injection экранируется

---

## S1. Repositories (state)

### T-S03-006. StatusHistoryRepository (Protocol + InMemory)

Target:
- `src/fe_bot/setup/source_registry/status_history.py`
- `tests/unit/test_status_history_repository.py`

```python
class StatusHistoryRepository(Protocol):
    def append(self, entry: SourceStatusHistoryEntry) -> None: ...
    def list_for_document(self, source_document_id: str) -> list[SourceStatusHistoryEntry]: ...
    def get_by_event_id(self, event_id: str) -> SourceStatusHistoryEntry | None: ...

class InMemoryStatusHistoryRepository:
    # idempotent по event_id (повторный append возвращает существующий)
    # thread-safe (threading.Lock)
    # сохраняет порядок (chronological)
```

Acceptance:
- 5 unit-тестов: append, list, idempotency by event_id, get_by_event_id, thread safety

### T-S03-007. ProcessingLogRepository (Protocol + InMemory)

Target:
- `src/fe_bot/setup/source_registry/processing_log.py`
- `tests/unit/test_processing_log_repository.py`

Идентично StatusHistory + filtering by step/level/setup_job_id.

Acceptance:
- 6 unit-тестов

### T-S03-008. LineageRepository (Protocol + InMemory)

Target:
- `src/fe_bot/setup/source_registry/lineage.py`
- `tests/unit/test_lineage_repository.py`

```python
class LineageRepository(Protocol):
    def link(self, relation: SourceLineageRelation) -> SourceLineageRelation: ...
    def list_for_source(self, source_document_id: str) -> list[SourceLineageRelation]: ...
    def list_by_target(self, target_type: str, target_id: str) -> list[SourceLineageRelation]: ...
    def counters(self, source_document_id: str) -> dict[str, int]: ...

class InMemoryLineageRepository:
    # unique key: (source_id, target_type, target_id, relation_type)
    # повторный link не создаёт дубликаты — возвращает existing
```

Acceptance:
- 6 unit-тестов включая unique constraint

---

## S2. Service expansion

### T-S03-009. SourceRegistryService.update_status

Target:
- `src/fe_bot/setup/source_registry/service.py` (расширение)
- `tests/unit/test_source_registry_status.py`

Метод:
```python
def update_status(
    self, *,
    source_document_id: str,
    new_status: SourceDocumentStatus,
    event_id: str,
    reason: str | None = None,
    changed_by_type: str = "service",
    changed_by_id: str = "unknown",
    metadata: dict | None = None,
) -> SourceDocument:
    # 1. Get current document
    # 2. validate_transition(current.status, new_status) — иначе InvalidStatusTransition
    # 3. idempotency: if event_id уже есть в history — return existing
    # 4. Update document.status
    # 5. Append status history entry (atomic)
    # 6. Return updated document
```

Также `InvalidStatusTransitionError(LookupError)`.

Acceptance:
- 8 тестов: success, invalid transition, idempotency, atomicity (history-then-status или ничего), unknown document

### T-S03-010. SourceRegistryService.append_log + link_artifact + get_lineage

Target:
- `src/fe_bot/setup/source_registry/service.py`
- `tests/unit/test_source_registry_lineage.py`

Методы:
```python
def append_processing_log(self, entry: SourceProcessingLogEntry) -> SourceProcessingLogEntry  # idempotent
def link_artifact(self, *, source_id, event_id, target_type, target_id, relation_type, created_by_service, metadata={}) -> SourceLineageRelation  # idempotent
def get_lineage(self, source_document_id: str) -> SourceLineageSummary  # with counters
def list_for_target(self, target_type, target_id) -> list[SourceLineageRelation]  # reverse lookup
```

Acceptance:
- 8 тестов

### T-S03-011. SourceRegistryService.update_user_metadata

Target:
- `src/fe_bot/setup/source_registry/service.py`
- `tests/unit/test_source_registry_metadata.py`

```python
def update_user_metadata(
    self, *,
    source_document_id: str,
    patch: dict,  # только tags, description, owner_note, custom_labels
    updated_by: str,
) -> SourceDocument:
    # 1. Get document
    # 2. Validate patch — отклонить protected fields (checksum, status, storage_path, etc.)
    # 3. Merge user_metadata
    # 4. Update document.updated_at
    # 5. Append processing log (optional, INFO level)
    # 6. Return updated
```

`SystemMetadataReadOnlyError`.

Acceptance:
- 6 тестов: success patch, protected field rejected (5 cases), идемпотентность

---

## S3. Read endpoints (under /sources)

### T-S03-012. GET /api/v1/setup/{sid}/sources

Target:
- `src/fe_bot/api/setup/sources_router.py` (новый файл)
- `src/fe_bot/api/setup/sources_dto.py` (новый — DTOs для responses)
- `tests/integration/test_list_sources.py`

Endpoint:
```
GET /api/v1/setup/{setup_job_id}/sources
  ?status=registered,parsing  (multi-select)
  &document_kind=schema
  &content_type=text/markdown
  &owner=user_xxx
  &has_errors=true
  &has_rag_cards=true
  &include_removed=false
  &page=1
  &page_size=20
  &sort=uploaded_at:desc
```

Response: `SourceDocumentListResponse` с `SourceDocumentListItemDTO` (включая counters из lineage).

Acceptance:
- 10 integration-тестов: happy path, фильтры (status, document_kind, has_errors), pagination, sort, 403, 404, include_removed, empty result

### T-S03-013. GET /api/v1/setup/{sid}/sources/{src_id}

Target:
- `sources_router.py` + `sources_dto.py`
- `tests/integration/test_get_source_details.py`

Response: `SourceDocumentDetailsDTO` с полной metadata (user + system), counters, last status history entry, last processing log entries (top 5).

Acceptance:
- 6 тестов: happy path, 404 (unknown), 404 (cross-job), 403, masked storage_path для non-admin, removed document still readable

### T-S03-014. GET /sources/{id}/status-history

Target:
- `sources_router.py`
- `tests/integration/test_status_history_endpoint.py`

Response: paginated `SourceStatusHistoryDTO`. Поддержка `?since=` фильтра.

Acceptance:
- 5 тестов

### T-S03-015. GET /sources/{id}/processing-log + GET /sources/{id}/lineage

Target:
- `sources_router.py`
- `tests/integration/test_processing_log_endpoint.py`
- `tests/integration/test_lineage_endpoint.py`

Processing log: paginated, фильтры по step/level. Lineage: relations + counters.

Acceptance:
- 5 + 4 тестов

---

## S4. Mutating endpoints + permissions

### T-S03-016. kb.source.* permissions family

Target:
- `src/fe_bot/auth/permissions.py`
- `tests/unit/test_auth_permissions.py`

Добавить:
- `KB_SOURCE_LIST = "kb.source.list"`
- `KB_SOURCE_READ = "kb.source.read"`
- `KB_SOURCE_METADATA_UPDATE = "kb.source.metadata.update"`
- `KB_SOURCE_REMOVE = "kb.source.remove"` (отдельно от KB_DOCUMENT_DELETE — finer grain)
- `KB_SOURCE_LINEAGE_READ = "kb.source.lineage.read"`
- `KB_SOURCE_LOG_READ = "kb.source.log.read"`

Распределение по ролям:
- USER: list, read, metadata_update, remove
- DOMAIN_EXPERT: + lineage_read, log_read
- RAG_ADMIN: все
- AUDITOR: list, read, lineage_read, log_read (read-only)

Acceptance:
- Все 6 permissions работают
- Update тестов permissions

### T-S03-017. PATCH /api/v1/setup/{sid}/sources/{src_id}/metadata

Target:
- `sources_router.py`
- `tests/integration/test_patch_source_metadata.py`

Запрещённые поля → 400 INVALID_METADATA_PATCH. Audit event `SOURCE_METADATA_UPDATED`.

Acceptance:
- 8 тестов: happy path, отклонение protected fields (5 кейсов), 403, 404, idempotency, max length

### T-S03-018. DELETE /api/v1/setup/{sid}/sources/{src_id}

Target:
- `sources_router.py`
- `tests/integration/test_delete_source.py`

Delegate to существующий `DocumentUploadService.remove_document` (уже soft-delete с lineage check).

Расширить логику: блокировать удаление, если документ в статусе PUBLISHED (lineage с KNOWLEDGE_BASE_VERSION).

Acceptance:
- 5 тестов: happy path, published → 409 (DOCUMENT_ALREADY_PUBLISHED), unknown → 404, 403

---

## S5. Downstream integration + retry + events

### T-S03-019. DocumentUploadService → SourceRegistryService integration

Target:
- `src/fe_bot/setup/upload/service.py` (модификация)
- `tests/integration/test_upload_to_registry_flow.py`

Изменения: после `_registry.add(document)` сразу вызывать:
- `update_status(new_status=REGISTERED, event_id="upload:<doc_id>", changed_by_type="service", changed_by_id="document-upload-service")`
- `append_processing_log(step=UPLOAD, level=INFO, message="Document uploaded", event_id="upload:<doc_id>")`

Acceptance:
- 4 integration: upload → registry создаёт записи в history + log, retry не создаёт дубликатов

### T-S03-020. source.document.* events publication

Target:
- `src/fe_bot/setup/source_registry/events.py` (новый)
- `tests/integration/test_source_events.py`

EventBus events:
- `source.document.registered`
- `source.document.status_changed`
- `source.document.metadata_updated`
- `source.document.lineage_updated`
- `source.document.processing_failed`
- `source.document.removed`

DTOs матчат §16.2 спека.

Acceptance:
- 6 тестов: каждое event публикуется на правильный trigger, payload корректный

### T-S03-021. POST /api/v1/setup/{sid}/sources/{src_id}/retry

Target:
- `sources_router.py`
- `src/fe_bot/setup/source_registry/service.py` (.retry_processing)
- `tests/integration/test_source_retry.py`

Endpoint:
```
POST /api/v1/setup/{sid}/sources/{src_id}/retry?from_step=parsing
```

Логика:
- Если status не PROCESSING_FAILED / PARSE_FAILED — 409
- Reset status to соответствующий waiting (WAITING_FOR_PARSING для parsing retry)
- Append history + log
- Эмиттит event для downstream re-trigger (downstream сервисы появятся в SETUP-04+)

Acceptance:
- 5 тестов: happy path, wrong status → 409, unknown → 404, 403, повторный retry idempotent по event_id

### T-S03-022. Audit + metrics для новых actions

Target:
- `src/fe_bot/audit/service.py`
- `src/fe_bot/setup/source_registry/service.py` (audit hooks)
- `tests/integration/test_source_audit_metrics.py`

Новые AuditAction:
- `STATUS_CHANGED`
- `METADATA_UPDATED`
- `LINEAGE_ADDED`
- `PROCESSING_RETRY_TRIGGERED`

Метрики:
- Counter `source_documents_total{status}`
- Counter `source_status_changes_total{from_status,to_status}`
- Counter `source_processing_failures_total{step,error_code}`
- Counter `source_lineage_relations_total{target_type}`
- Histogram `source_registry_api_latency_seconds{endpoint}`

Acceptance:
- 6 тестов: audit для каждой action, metric incremented

---

## S6. Frontend

### T-S03-023. API client + types extension

Target:
- `frontend/src/api/types.ts`
- `frontend/src/api/sources.ts` (новый)
- `frontend/src/test/msw.ts` (handlers)

TypeScript типы для всех новых DTOs (status history, processing log, lineage). API client functions: `listSources`, `getSource`, `getStatusHistory`, `getProcessingLog`, `getLineage`, `patchSourceMetadata`, `deleteSource`, `retrySource`.

Acceptance:
- 6 functions, typecheck passes, MSW handlers для всех 7 endpoints

### T-S03-024. SourceRegistryTab + SourceDocumentTable

Target:
- `frontend/src/components/SourceRegistry/SourceRegistryTab.tsx`
- `frontend/src/components/SourceRegistry/SourceDocumentTable.tsx`
- `frontend/src/components/Wizard/steps/UploadDocumentsStep.tsx` (интеграция)
- Tests

Колонки (см. §10.1): filename, document_kind, content_type, size, checksum_short, owner, uploaded_at, current_status (badge), parsed_sections_count, rag_cards_count, last_error, actions.

Фильтры: status (multi), document_kind, owner, has_errors, has_rag_cards.

Actions: Details, Delete, Retry (if failed).

Acceptance:
- 10 unit-тестов компонентов

### T-S03-025. SourceDocumentDetailsDrawer (с 5 табами)

Target:
- `frontend/src/components/SourceRegistry/SourceDocumentDetailsDrawer.tsx`
- 5 panel-компонентов: Overview, Metadata, StatusHistory, ProcessingLog, Lineage
- Tests

Каждая panel загружается lazy при переключении табов.

Acceptance:
- 12 unit-тестов

### T-S03-026. User metadata editor + retry button

Target:
- `frontend/src/components/SourceRegistry/MetadataEditor.tsx`
- `frontend/src/components/SourceRegistry/RetryButton.tsx`
- Tests

Metadata editor: tags multi-input, description textarea, owner_note input, validation на длину, optimistic updates с rollback.

Retry button: confirm dialog → POST /retry, обновляет status в таблице.

Acceptance:
- 8 unit-тестов

---

## S7. Resilience + docs + final verify

### T-S03-027. Resilience tests

Target:
- `tests/integration/test_source_registry_resilience.py`

Сценарии:
- Invalid status transitions (5 разных) → 409 + audit
- Duplicate event_id (status update, log, lineage) — все idempotent
- Status history write failed — status rollback (atomicity)
- Cross-job lineage не создаётся
- Lineage с несуществующим target → warning + reject
- Concurrent updates same document — последний event_id побеждает
- DELETE published source → 409
- PATCH metadata XSS payload → sanitized

Acceptance:
- 12 resilience-тестов

### T-S03-028. Documentation + traceability matrix

Target:
- `docs/02-system/features/SETUP-03-source-registry.md` (обновить с полным детальным контентом из приложенного спека)
- `docs/traceability/setup-03.md` (новый — 34 AC → impl → tests + 29 tasks → files → tests + 7 endpoints + 6 events)
- Обновить `docs/implementation-plan/README.md`

Acceptance:
- Все 34 AC из §19 спека трассированы
- Все 29 tasks трассированы
- Документация на русском

### T-S03-029. Final verify (pytest + mypy + ruff + npm)

Target: запустить полный gate.

Acceptance:
- `pytest tests/` — все проходят (ожидается ~720+ тестов после S0..S7)
- `mypy --strict schemas/ validators/ src/` — 0 errors
- `ruff check schemas/ validators/ src/ tests/` — 0 errors
- `npm run typecheck && npm test && npm run build` — green
- Backend regression: 100% старых SETUP-01/02 тестов проходят

---

## Прогресс summary

```
S0 ✓ 0/5  S1 ✓ 0/3  S2 ✓ 0/3  S3 ✓ 0/4  S4 ✓ 0/3  S5 ✓ 0/4  S6 ✓ 0/4  S7 ✓ 0/3
0/29 задач (0%)
```

## Зависимости

- SETUP-01 ✓ closed (auth, permissions, repositories, audit, metrics)
- SETUP-02 ✓ closed (upload flow, BatchRegistry, SourceDocument schema)
- INF-002 (PostgreSQL миграция) — отложено
- INF-005 (Kafka) — отложено

## Risks

- **Status enum расширение** (T-S03-001) меняет SETUP-01 pipeline (status-зависимые узлы). Mitigation: сохранить старые статусы + добавить новые без breaking.
- **Lineage с несуществующими targets** до SETUP-04/05 — все lineage-relations пока **простые stubs** с явной target validation; реальные RAG Card / Parsed Section появятся позже.
- **PATCH metadata XSS** — Pydantic + custom sanitizer на serialize; покрыто T-S03-027.
- **Retry endpoint без downstream pipeline** — endpoint emits event, но downstream сервисов (parser, generator) ещё нет; retry в MVP работает только на status reset + log entry. Реальный re-trigger downstream в SETUP-04+.
