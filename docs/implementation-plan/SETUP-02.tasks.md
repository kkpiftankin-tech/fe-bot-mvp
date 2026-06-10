# План реализации SETUP-02. Загрузка исходных документов через фронт

Реализация фичи [SETUP-02](../02-system/features/SETUP-02-document-upload.md) (документ приложен пользователем; mojibake decoded). SETUP-02 — это **прицельное расширение** S2 «Document Upload» из SETUP-01: добавляет batch-tracking, второй уровень валидации, аудит/метрики upload-flow, DELETE/retry endpoints, drag-and-drop UI и duplicate-policy dialog.

Не относится к SETUP-02: парсинг, генерация RAG-карточек, chunking, embedding, KB publish — это покрывается SETUP-04..11.

## Gap-анализ vs текущий код

| Требование SETUP-02 | Текущее состояние | Действие |
|---|---|---|
| `POST /api/setup/{id}/documents` (multipart) | ✅ Реализован в S2 (T-S01-013) | Расширить response shape (summary + per-file errors) |
| `GET /api/setup/{id}/documents` | ✅ Реализован в S2 (T-S01-015) | Без изменений |
| `DELETE /api/setup/{id}/documents/{id}` | ❌ Отсутствует | **Новый endpoint** |
| `POST /api/setup/{id}/documents/retry` | ❌ Отсутствует | **Новый endpoint** (опционально MVP) |
| `GET /api/setup/{id}/documents/{id}` (metadata) | ❌ Отсутствует | **Новый endpoint** |
| `UploadBatchDTO` (files_total / uploaded / rejected / duplicates) | ❌ Отсутствует | **Новая сущность + репозиторий** |
| `upload_request_id` idempotency | ❌ Отсутствует | Добавить в DocumentUploadService |
| Валидация: extensions allowlist | ✅ Базовая (`upload/validation.py`) | Расширить allowlist + per-extension MIME map |
| Валидация: filename safety (path traversal) | ⚠️ Частично | Добавить strict normalization |
| Валидация: batch size / count limits | ❌ Отсутствует | Добавить в Document Upload Service |
| Валидация: filename uniqueness в batch | ❌ Отсутствует | Добавить в roiuter handler |
| Per-file error codes (`UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, …) | ⚠️ Текстовые сообщения | Структурированный `error_code` enum + `details` |
| SHA-256 checksum | ✅ В DocumentUploadService | Без изменений |
| Duplicate detection (skip) | ✅ DuplicateStrategy.SKIP в S2 | Добавить duplicate-policy в response |
| `upload_as_new_version` policy | ✅ В коде есть `NEW_VERSION` | Активировать в endpoint через query param |
| `replace_existing` policy | ✅ В коде есть `REPLACE` | Активировать в endpoint через query param |
| Audit events `setup.document.uploaded/rejected/duplicate/removed` | ⚠️ Только uploaded через EventBus | Подключить AuditService из S8 + 4 события |
| Metrics: upload_*_total counters / latency histogram | ❌ Отсутствует | Подключить MetricsRegistry из S8 |
| Frontend: file picker (basic) | ✅ S7 `UploadDocumentsStep` | Расширить до drag-and-drop |
| Frontend: per-file progress | ❌ Отсутствует | Новый `UploadProgressList` |
| Frontend: `UploadedFilesTable` с actions | ⚠️ Простой `<ul>` | Полноценная таблица + delete/retry actions |
| Frontend: `FileValidationErrorsPanel` | ⚠️ Inline error | Отдельная панель с per-file errors |
| Frontend: `DuplicateFileDialog` | ❌ Отсутствует | Модалка skip/version/replace (MVP — только skip) |
| Cleanup orphaned files | ❌ Отсутствует | Background task или admin endpoint |
| Document статус `REMOVED` | ❌ В enum есть `ARCHIVED` | Добавить `REMOVED` status в SourceDocumentStatus |

**Итого:** 7 endpoints (3 новых, 1 расширен), 1 новая сущность, 6 расширений сервисов, 5 новых UI-компонентов, audit/metrics wiring, ~25 тестов.

---

## Логика слайсов

```text
S0. DTO + status enum + UploadBatch schema           → 3 задачи
S1. Backend validation extensions + idempotency      → 4 задачи
S2. UploadBatch persistence + расширенный response   → 3 задачи
S3. Audit + Metrics wiring для upload-flow           → 3 задачи
S4. DELETE / retry / GET metadata endpoints          → 3 задачи
S5. Frontend: drag-and-drop + per-file progress      → 3 задачи
S6. Frontend: UploadedFilesTable + duplicate dialog  → 3 задачи
S7. Resilience: orphan cleanup + tests + docs        → 3 задачи
```

Итого 25 задач (T-S02-001..T-S02-025). Cross-cutting INF задачи переиспользуются из SETUP-01.

---

## S0. Контракты и схемы

### T-S02-001. UploadBatchDTO + UploadBatchStatus

Target:
- `schemas/setup/upload_batch.py` (новый DTO)
- `schemas/setup/source_document.py` (добавить `REMOVED`, `FAILED_VALIDATION` статусы)
- `tests/unit/test_upload_batch_schema.py`

Содержание:
```python
class UploadBatchStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"

class UploadBatch(BaseModel):
    upload_batch_id: str
    setup_job_id: str
    user_id: str
    upload_request_id: str | None  # idempotency token
    status: UploadBatchStatus
    files_total: int
    files_uploaded: int
    files_rejected: int
    duplicates_detected: int
    created_at: datetime
    finished_at: datetime | None
```

Acceptance:
- `extra="forbid"`, `frozen=True` после `finished_at != None`.
- `UploadBatchStatus` транзишены: IN_PROGRESS → COMPLETED/PARTIALLY_COMPLETED/FAILED.
- 6+ unit-тестов.

### T-S02-002. Error code enum + UploadFileErrorDTO

Target:
- `schemas/setup/upload_errors.py` (новый)
- `tests/unit/test_upload_errors.py`

Содержание:
```python
class UploadErrorCode(StrEnum):
    MISSING_FILES = "MISSING_FILES"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    BATCH_TOO_LARGE = "BATCH_TOO_LARGE"
    EMPTY_FILE = "EMPTY_FILE"
    INVALID_FILENAME = "INVALID_FILENAME"
    DUPLICATE_FILE = "DUPLICATE_FILE"
    SETUP_JOB_NOT_FOUND = "SETUP_JOB_NOT_FOUND"
    SETUP_JOB_NOT_UPLOADABLE = "SETUP_JOB_NOT_UPLOADABLE"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    OBJECT_STORAGE_UNAVAILABLE = "OBJECT_STORAGE_UNAVAILABLE"
    OBJECT_STORAGE_WRITE_FAILED = "OBJECT_STORAGE_WRITE_FAILED"
    SOURCE_REGISTRY_UNAVAILABLE = "SOURCE_REGISTRY_UNAVAILABLE"
    CHECKSUM_CALCULATION_FAILED = "CHECKSUM_CALCULATION_FAILED"
    UPLOAD_STREAM_INTERRUPTED = "UPLOAD_STREAM_INTERRUPTED"
    INTERNAL_UPLOAD_ERROR = "INTERNAL_UPLOAD_ERROR"

class UploadFileError(BaseModel):
    filename: str
    error_code: UploadErrorCode
    message: str
    details: dict[str, Any] = {}
```

Acceptance:
- Все коды покрыты unit-тестами на стабильность string-значения (контракт API).
- `details` поддерживает структурированные данные (allowed_extensions, current_size, max_size).

### T-S02-003. UploadDocumentsResponse v2 + миграция роутера

Target:
- `src/fe_bot/api/setup/dto.py` (расширить `UploadDocumentsResponse`)
- `tests/unit/test_upload_response_dto.py`

Содержание:
```python
class UploadSummary(BaseModel):
    files_total: int
    files_uploaded: int
    files_rejected: int
    duplicates_detected: int

class UploadDocumentsResponse(BaseModel):
    setup_job_id: str
    upload_batch_id: str
    summary: UploadSummary
    documents: list[SourceDocumentResponse]   # успешно загруженные
    duplicates: list[SourceDocumentResponse]  # обнаруженные duplicates (skip-полит.)
    errors: list[UploadFileError]             # rejected files
    job_status: SetupJobStatus
    message: str | None
```

Acceptance:
- Существующие S2-тесты `test_upload_documents.py` адаптированы (backward-compat: старые поля помечены deprecated, не удалены).
- Контракт-тест проверяет, что summary.files_total = uploaded + rejected + duplicates.

---

## S1. Backend validation + idempotency

### T-S02-004. Filename safety: path traversal + normalization

Target:
- `src/fe_bot/setup/upload/validation.py` (расширить)
- `tests/unit/test_upload_validation.py` (+5 кейсов)

Acceptance:
- Отклоняются: `../etc/passwd`, `..\\windows\\system32`, `/etc/hosts`, имена с null byte, control characters.
- Принимаются: `valid name.md`, `файл с пробелами.txt`, `data-2026-06-09.csv`.
- Длина filename ≤ 255 символов (POSIX limit).

### T-S02-005. Batch size + count limits

Target:
- `src/fe_bot/setup/upload/service.py` (новые exceptions + проверки)
- `schemas/common/defaults.py` (`MAX_BATCH_FILES_COUNT=50`, `MAX_TOTAL_BATCH_SIZE_BYTES=500MB`)
- `tests/unit/test_upload_batch_limits.py`

Acceptance:
- `BatchTooManyFilesError` если `len(files) > MAX_BATCH_FILES_COUNT`.
- `BatchTooLargeError` если sum(size_bytes) > `MAX_TOTAL_BATCH_SIZE_BYTES`.
- Лимиты конфигурируемы через `defaults.py`.
- Router возвращает `413 Payload Too Large` с error_code `BATCH_TOO_LARGE`.

### T-S02-006. Filename uniqueness внутри batch

Target:
- `src/fe_bot/api/setup/router.py` (расширить `upload_documents`)
- `tests/integration/test_upload_documents.py` (+1 кейс)

Acceptance:
- Если в batch есть `a.md`, `a.md` — второй получает `INVALID_FILENAME` с details `{duplicate_in_batch: true}`.
- Это check **до** обращения к Source Registry (не путать с cross-batch checksum-duplicate).

### T-S02-007. upload_request_id idempotency

Target:
- `src/fe_bot/setup/upload/service.py` (добавить `upload_request_id` параметр)
- `src/fe_bot/setup/upload/batch_registry.py` (новый — `InMemoryBatchRegistry`)
- `tests/integration/test_upload_idempotency.py`

Acceptance:
- Повторный POST c тем же `upload_request_id` возвращает кэшированный `UploadDocumentsResponse` (не запускает заново).
- TTL idempotency-кэша 1 час (configurable).
- Если `upload_request_id` отсутствует — генерируется автоматически и возвращается в response.

---

## S2. Batch persistence + расширенный response

### T-S02-008. UploadBatch repository (Protocol + InMemory)

Target:
- `src/fe_bot/setup/upload/batch_registry.py`
- `tests/unit/test_batch_registry.py`

Acceptance:
- Protocol: `add`, `get`, `update_status`, `list_for_job`, `get_by_request_id`.
- InMemory с deep-copy на чтение (защита от мутации).
- Counters инкрементятся атомарно (thread-safe).

### T-S02-009. Document Upload Service v2 — batch tracking + per-file results

Target:
- `src/fe_bot/setup/upload/service.py` (новый метод `upload_batch`)
- `tests/integration/test_upload_batch_flow.py`

Acceptance:
- Новый метод `upload_batch(*, setup_job_id, files: list[UploadInput], …) -> UploadBatchResult`.
- Старый `upload(single file)` сохранён для обратной совместимости.
- Partial success: один файл fail → batch.status = PARTIALLY_COMPLETED, остальные сохраняются.
- Полный fail → batch.status = FAILED, никаких orphaned files в storage.
- Транзакционная гарантия: storage.upload + registry.add либо обе успешны, либо обе откатываются.

### T-S02-010. Router: обновлённый POST /documents

Target:
- `src/fe_bot/api/setup/router.py`
- `tests/integration/test_upload_documents.py` (обновить ожидания)
- `tests/contract/test_upload_endpoint_contract.py`

Acceptance:
- Query params: `duplicate_strategy` (skip/replace/new_version), `upload_request_id` (optional).
- Response shape v2 (summary + documents + duplicates + errors).
- Контракт-тест: OpenAPI schema matches actual responses.

---

## S3. Audit + Metrics для upload-flow

### T-S02-011. Audit hooks в DocumentUploadService

Target:
- `src/fe_bot/setup/upload/service.py` (DI AuditService)
- `src/fe_bot/audit/service.py` (новые AuditAction: `DOCUMENT_REMOVED`, `DOCUMENT_REPLACED`, `BATCH_COMPLETED`)
- `tests/integration/test_upload_audit.py`

Acceptance:
- Каждый upload пишет `DOCUMENT_UPLOADED` с payload {source_document_id, size_bytes, checksum}.
- Каждый reject пишет `DOCUMENT_REJECTED` с payload {error_code, filename}.
- Каждый duplicate пишет `DOCUMENT_DUPLICATE_SKIPPED` с payload {existing_doc_id, checksum}.
- DELETE пишет `DOCUMENT_REMOVED` с reason.
- Batch completion пишет `BATCH_COMPLETED` с summary.

### T-S02-012. Metrics для upload-flow

Target:
- `src/fe_bot/setup/upload/service.py` (DI MetricsRegistry)
- `tests/integration/test_upload_metrics.py`

Counters:
- `upload_requests_total{strategy}`
- `upload_files_total{outcome}` (uploaded/rejected/duplicate)
- `upload_bytes_total{outcome}`
- `upload_errors_total{error_code}`

Histograms:
- `upload_latency_seconds{phase}` (validation, checksum, storage, registry, total)
- `upload_file_size_bytes`

Acceptance:
- После 3 успешных upload в `/metrics` есть `upload_files_total{outcome="uploaded"} 3.0`.
- После 1 too-large upload есть `upload_errors_total{error_code="FILE_TOO_LARGE"} 1.0`.

### T-S02-013. Structured logging для upload-flow

Target:
- `src/fe_bot/setup/upload/service.py`
- `tests/unit/test_upload_logging.py`

Acceptance:
- Каждый upload-event логируется с полями: setup_job_id, source_document_id, filename, size_bytes, checksum, status, duration_ms.
- correlation_id propagates из middleware (S8).
- JSON-формат (см. T-S01-050).

---

## S4. DELETE / retry / GET metadata endpoints

### T-S02-014. DELETE /api/v1/setup/{id}/documents/{doc_id}

Target:
- `src/fe_bot/api/setup/router.py` (новый endpoint)
- `src/fe_bot/setup/upload/service.py` (новый метод `remove_document`)
- `src/fe_bot/api/setup/dto.py` (`RemoveDocumentResponse`)
- `tests/integration/test_remove_document.py`

Acceptance:
- Permission: `kb.document.delete` (новый Permission в enum).
- Только owner job или admin может удалять.
- Запрещено если job.status not in {DRAFT, FILES_UPLOADED} → 409.
- Документ помечается `status=REMOVED`, объект в storage удаляется.
- Audit event `DOCUMENT_REMOVED`.
- 5+ тестов (happy path, 404, 403, 409, idempotent повтор).

### T-S02-015. GET /api/v1/setup/{id}/documents/{doc_id}

Target:
- `src/fe_bot/api/setup/router.py` (новый endpoint)
- `tests/integration/test_get_document_metadata.py`

Acceptance:
- Permission: `kb.document.read`.
- Возвращает полный `SourceDocumentResponse` (без бинарного содержимого).
- `storage_path` маскируется для не-admin (через `_to_doc_response(include_storage_path=False)`).

### T-S02-016. POST /api/v1/setup/{id}/documents/retry (опционально MVP)

Target:
- `src/fe_bot/api/setup/router.py`
- `tests/integration/test_retry_upload.py`

Acceptance:
- Принимает list of `source_document_id` со статусом `FAILED`.
- Повторно прогоняет через DocumentUploadService с тем же binary content (читает из storage если ещё есть, иначе требует re-upload).
- Если статус не FAILED → 409.

**Опционально MVP**: если решим отложить — оставляем заглушку с 501 и переносим в SETUP-03.

---

## S5. Frontend: drag-and-drop + per-file progress

### T-S02-017. FileUploadPanel с drag-and-drop

Target:
- `frontend/src/components/Upload/FileUploadPanel.tsx` (новый)
- `frontend/src/components/Wizard/steps/UploadDocumentsStep.tsx` (заменить file picker)
- `frontend/src/components/Upload/__tests__/FileUploadPanel.test.tsx`

Acceptance:
- Drag-and-drop с visual feedback (hover, dragging states).
- Fallback file picker (button).
- Client-side preview списка выбранных файлов с per-file size + extension.
- Disabled state если `setup_job_id == null` или statuses не позволяют upload.
- Подсказка с allowed extensions + max size (config from backend).

### T-S02-018. UploadProgressList — per-file progress bars

Target:
- `frontend/src/components/Upload/UploadProgressList.tsx`
- `frontend/src/hooks/useUploadProgress.ts` (custom hook вокруг XHR progress event)
- `frontend/src/components/Upload/__tests__/UploadProgressList.test.tsx`

Acceptance:
- Per-file progress bar (0-100%) во время upload.
- States: uploading / uploaded / rejected / duplicate с цветовой кодировкой.
- Использует `XMLHttpRequest.upload.onprogress` (fetch API не даёт progress).
- Отображает per-file error code + message при reject.

### T-S02-019. Client-side validation rules

Target:
- `frontend/src/lib/uploadValidation.ts` (новый)
- `frontend/src/lib/__tests__/uploadValidation.test.ts`

Rules:
- Extension в allowlist.
- Size ≤ MAX_FILE_SIZE.
- Filename не пустой, не содержит control chars.
- Batch size + count limits.
- Duplicate filename detection в текущем batch.

Acceptance:
- Pure functions, без зависимости от React.
- Возвращает `{valid: true} | {valid: false, errors: UploadValidationError[]}`.
- 10+ unit-тестов покрывают все правила.

---

## S6. Frontend: UploadedFilesTable + duplicate dialog

### T-S02-020. UploadedFilesTable

Target:
- `frontend/src/components/Upload/UploadedFilesTable.tsx`
- `frontend/src/components/Upload/__tests__/UploadedFilesTable.test.tsx`

Columns: filename, content_type, size, checksum (truncated), status badge, uploaded_at, actions.

Actions:
- Delete (calls DELETE /documents/{id}, confirmation dialog).
- Retry (для FAILED — calls POST /documents/retry).
- Details (modal с полной metadata, storage_path для admin).

Acceptance:
- Sortable по filename, size, uploaded_at.
- Filter по status (uploaded/rejected/duplicate/removed).
- Empty state с подсказкой.
- 8+ tests (sort, filter, delete confirmation, retry, details modal).

### T-S02-021. FileValidationErrorsPanel

Target:
- `frontend/src/components/Upload/FileValidationErrorsPanel.tsx`
- `frontend/src/components/Upload/__tests__/FileValidationErrorsPanel.test.tsx`

Acceptance:
- Summary banner: "Загружено N из M, ошибок: K, дубликатов: L".
- Per-file expandable error с error_code + message + suggested action.
- Кнопка "Очистить" — убирает rejected files из локального state.

### T-S02-022. DuplicateFileDialog (MVP — skip-only)

Target:
- `frontend/src/components/Upload/DuplicateFileDialog.tsx`
- `frontend/src/components/Upload/__tests__/DuplicateFileDialog.test.tsx`

MVP behavior:
- Срабатывает если backend response содержит duplicates с подсказкой принять решение.
- Один выбор: "Пропустить дубликат" (default) + ссылка на оригинальный документ.
- Опции `Заменить` и `Новая версия` помечены `feature_flag` (выключены в MVP).

Acceptance:
- Доступная для keyboard navigation (Tab / Enter / Esc).
- `aria-modal="true"`, focus trap.

---

## S7. Resilience + tests + docs

### T-S02-023. Orphan file cleanup (admin endpoint + background helper)

Target:
- `src/fe_bot/api/observability/router.py` (новый endpoint `POST /admin/cleanup/orphans`)
- `src/fe_bot/setup/upload/cleanup.py` (новый — `find_orphans`, `delete_orphans`)
- `tests/integration/test_orphan_cleanup.py`

Acceptance:
- Сравнивает list of storage objects vs list of SourceDocument в registry.
- Объекты без записи в registry > TTL (24h) удаляются.
- Endpoint требует `Permission.ADMIN_ONLY`.
- Background-task (для INF-002) — APScheduler hook stub.

### T-S02-024. Negative & resilience tests

Target:
- `tests/integration/test_upload_resilience.py`

Сценарии:
- Object Storage unavailable → 500, no SourceDocument created, no metric incremented as "uploaded".
- Source Registry transient error → retry → success.
- Network timeout (симулируется через respx) → idempotent retry returns same result.
- MIME spoofing (content_type=md, magic bytes=PDF) → reject by content sniffing.
- Concurrent upload of same checksum from 2 batches → один зафиксирован, второй duplicate.
- Batch с 51 файлом (limit=50) → 413 BATCH_TOO_LARGE.
- Total batch size 501MB (limit=500MB) → 413.

Acceptance:
- 10+ resilience-кейсов проходят.

### T-S02-025. Documentation + traceability update

Target:
- `docs/02-system/features/SETUP-02-document-upload.md` (положить русскую версию из приложения)
- `docs/07-contracts/dto-catalog.md` (добавить `UploadBatchDTO`, `UploadFileError`)
- `docs/07-contracts/api-contracts.md` (новые endpoints)
- `docs/traceability/setup-02.md` (новый — каждое AC → файл + тест)
- `AGENTS.md` (no changes — SETUP-02 не использует LLM-агентов)

Acceptance:
- Все 30 Acceptance Criteria из §19 спецификации трассируются как минимум в 1 файл + 1 тест.
- Diff в `dto-catalog.md` помечен `[SETUP-02]`.

---

## Открытые вопросы (из §22.3 спецификации)

| Вопрос | Дефолт для MVP | Кто решает |
|---|---|---|
| MAX_FILE_SIZE_BYTES | 100MB (уже в `defaults.py`) | Product Owner |
| MAX_BATCH_FILES_COUNT | 50 | Architect |
| MAX_TOTAL_BATCH_SIZE_BYTES | 500MB | Architect |
| Versioning (upload_as_new_version) | Реализовать, но скрыть за feature flag | Product Owner |
| Antivirus scanning | **Не в MVP**; stub-hook `virus_scan_hook` | Security |
| Preview содержимого | **Не в MVP** | Product Owner / UX |
| DMS integration | **Не в MVP** | Product Owner |
| TTL для removed/failed files | 7 дней | DevOps |
| Frontend checksum (UX) | Не считать на frontend в MVP (нагрузка на browser) | Frontend Lead |

Все дефолты записаны в `schemas/common/defaults.py` с маркером `# TODO[SETUP-02-Qx]` для последующего ADR.

---

## Зависимости

| Слайс | Зависит от |
|---|---|
| S0 | SETUP-01 S0 (DTO infrastructure) |
| S1 | S0 |
| S2 | S1, SETUP-01 S2 (existing DocumentUploadService) |
| S3 | S2, SETUP-01 S8 (AuditService + MetricsRegistry) |
| S4 | S2 |
| S5 | SETUP-01 S7 (frontend scaffold) |
| S6 | S5 + S4 |
| S7 | S2 + S4 |

**Параллелизация:**
- Backend (S0..S4) и Frontend (S5..S6) могут идти параллельно после S0 готова.
- S3 (audit/metrics) и S4 (DELETE/retry) — независимы, могут идти параллельно.

---

## Critical path

```text
S0 (3 задачи, 1 день) →
S1 (4 задачи, 1.5 дня) →
S2 (3 задачи, 1.5 дня) →
S3 + S4 parallel (6 задач, 2 дня) →
S5 + S6 parallel (6 задач, 2.5 дня) →
S7 (3 задачи, 1.5 дня)
```

Оценка: **~10 рабочих дней** для одного разработчика, **~6 дней** при параллельной работе Backend + Frontend + QA.

---

## Acceptance Gate для SETUP-02 целиком

```text
✓ pytest tests/                          → +25 новых тестов (455 → 480+)
✓ mypy --strict                          → 0 errors
✓ ruff check                             → 0 errors
✓ frontend npm test                      → +15 новых тестов (7 → 22+)
✓ npm run typecheck + build              → 0 errors
✓ Все 30 AC из §19 спецификации          → trace → файл + тест
✓ Audit log содержит все upload events   → integration test
✓ Metrics /metrics показывают upload_*   → integration test
✓ Frontend E2E: drag-and-drop → upload   → vitest
✓ Resilience: 10 negative scenarios pass → integration test
✓ Документация обновлена                 → docs/02-system + docs/07-contracts + docs/traceability
```
