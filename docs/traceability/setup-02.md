# SETUP-02 Traceability Matrix

Связь каждого артефакта SETUP-02 «Загрузка документов через фронт» с
implementation файлами и тестами. Поддерживается в актуальном состоянии при
изменении фичи.

**Спецификация:** [docs/02-system/features/SETUP-02-document-upload.md](../02-system/features/SETUP-02-document-upload.md)
**План:** [docs/implementation-plan/SETUP-02.tasks.md](../implementation-plan/SETUP-02.tasks.md)

## Acceptance Criteria → реализация → тест

### Доступ и запуск

| AC | Реализация | Тест |
|---|---|---|
| AC-01 user с `kb.document.upload` видит компонент | [auth/permissions.py](../../src/fe_bot/auth/permissions.py) (USER role); [Upload/FileUploadPanel.tsx](../../frontend/src/components/Upload/FileUploadPanel.tsx) | [test_auth_permissions.py](../../tests/unit/test_auth_permissions.py) |
| AC-02 user без permission получает 403 | [api/setup/router.py](../../src/fe_bot/api/setup/router.py) `require_permission(KB_DOCUMENT_UPLOAD)` | [test_upload_documents.py](../../tests/integration/test_upload_documents.py) |
| AC-03 upload доступен только в DRAFT/FILES_UPLOADED | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `_UPLOAD_ALLOWED_STATUSES` | [test_upload_documents.py](../../tests/integration/test_upload_documents.py) |

### Выбор файлов

| AC | Реализация | Тест |
|---|---|---|
| AC-04 file picker single file | [FileUploadPanel.tsx](../../frontend/src/components/Upload/FileUploadPanel.tsx) | [FileUploadPanel.test.tsx](../../frontend/src/components/Upload/__tests__/FileUploadPanel.test.tsx) |
| AC-05 file picker multi file | `<input multiple>` в FileUploadPanel.tsx | FileUploadPanel.test.tsx |
| AC-06 drag-and-drop | `onDragEnter`/`onDrop` в FileUploadPanel.tsx | FileUploadPanel.test.tsx |
| AC-07 список выбранных файлов | `selectedFiles` rendering в FileUploadPanel.tsx | FileUploadPanel.test.tsx |

### Client-side validation (T-S02-019)

| AC | Реализация | Тест |
|---|---|---|
| AC-08 отказ неподдерживаемого расширения | [lib/uploadValidation.ts](../../frontend/src/lib/uploadValidation.ts) `validateFile` | [uploadValidation.test.ts](../../frontend/src/lib/__tests__/uploadValidation.test.ts) |
| AC-09 отказ превышающего размер | `validateFile` → FILE_TOO_LARGE | uploadValidation.test.ts |
| AC-10 отказ пустого файла | `validateFile` → EMPTY_FILE | uploadValidation.test.ts |
| AC-11 partial success в batch | `partitionByValidation` + FileUploadPanel.onChange | uploadValidation.test.ts + FileUploadPanel.test.tsx |

### Backend validation (T-S02-004/005/006)

| AC | Реализация | Тест |
|---|---|---|
| AC-12 backend re-validates extension/MIME/size | [setup/upload/validation.py](../../src/fe_bot/setup/upload/validation.py) `validate_file` | [test_upload_validation.py](../../tests/unit/test_upload_validation.py) |
| AC-13 backend считает checksum | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `hashlib.sha256(data)` | [test_upload_documents.py](../../tests/integration/test_upload_documents.py) |
| AC-14 backend detects duplicate by checksum | [source_registry/service.py](../../src/fe_bot/setup/source_registry/service.py) `find_by_checksum` | [test_upload_documents.py](../../tests/integration/test_upload_documents.py) |
| AC-15 backend возвращает per-file result | [api/setup/router.py](../../src/fe_bot/api/setup/router.py) batch loop → `UploadDocumentsResponse v2` | [test_upload_batch_validation.py](../../tests/integration/test_upload_batch_validation.py) |

### Сохранение и регистрация

| AC | Реализация | Тест |
|---|---|---|
| AC-16 валидный файл сохраняется в Object Storage | [storage/artifact_service.py](../../src/fe_bot/storage/artifact_service.py) `InMemoryArtifactStorage.upload` | [test_artifact_storage.py](../../tests/integration/test_artifact_storage.py) |
| AC-17 создаётся SourceDocumentDTO | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) → `SourceDocument(...)` | [test_upload_documents.py](../../tests/integration/test_upload_documents.py) |
| AC-18 SourceDocumentDTO содержит обязательные поля | [schemas/setup/source_document.py](../../schemas/setup/source_document.py) | [test_source_document_schema.py](../../tests/unit/test_source_document_schema.py) |
| AC-19 setup job получает source_document_id | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `job.source_document_ids.append` | [test_upload_documents.py](../../tests/integration/test_upload_documents.py) |

### UI-результат

| AC | Реализация | Тест |
|---|---|---|
| AC-20 UI показывает status uploaded | [UploadProgressList.tsx](../../frontend/src/components/Upload/UploadProgressList.tsx) badges | [UploadProgressList.test.tsx](../../frontend/src/components/Upload/__tests__/UploadProgressList.test.tsx) |
| AC-21 UI показывает причину rejection | [FileValidationErrorsPanel.tsx](../../frontend/src/components/Upload/FileValidationErrorsPanel.tsx) | [FileValidationErrorsPanel.test.tsx](../../frontend/src/components/Upload/__tests__/FileValidationErrorsPanel.test.tsx) |
| AC-22 UI показывает duplicate | [DuplicateFileDialog.tsx](../../frontend/src/components/Upload/DuplicateFileDialog.tsx) + UploadProgressList | [DuplicateFileDialog.test.tsx](../../frontend/src/components/Upload/__tests__/DuplicateFileDialog.test.tsx) |
| AC-23 UI позволяет удалить до запуска pipeline | [UploadedFilesTable.tsx](../../frontend/src/components/Upload/UploadedFilesTable.tsx) Delete + DELETE endpoint | [test_delete_document.py](../../tests/integration/test_delete_document.py) + [UploadedFilesTable.test.tsx](../../frontend/src/components/Upload/__tests__/UploadedFilesTable.test.tsx) |
| AC-24 после refresh документы восстанавливаются | [api/setup/router.py](../../src/fe_bot/api/setup/router.py) `GET /documents` | [test_upload_documents.py](../../tests/integration/test_upload_documents.py) |

### Ошибки и resilience (T-S02-024)

| AC | Реализация | Тест |
|---|---|---|
| AC-25 Object Storage недоступен → понятная ошибка + retry option | [api/setup/router.py](../../src/fe_bot/api/setup/router.py) `except StorageError` → 500 + error_code | [test_upload_resilience.py](../../tests/integration/test_upload_resilience.py) |
| AC-26 Source Registry ошибка → не считать upload успешным | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `registry.add` → `storage.delete` rollback | [test_upload_resilience.py](../../tests/integration/test_upload_resilience.py) |
| AC-27 partial success: успешные сохраняются | [api/setup/router.py](../../src/fe_bot/api/setup/router.py) per-file errors → errors[]; uploaded остаются | [test_upload_batch_validation.py](../../tests/integration/test_upload_batch_validation.py) |

### Audit и аналитика (T-S02-011/012)

| AC | Реализация | Тест |
|---|---|---|
| AC-28 успешный upload → audit DOCUMENT_UPLOADED | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `_emit_uploaded` | [test_upload_audit.py](../../tests/integration/test_upload_audit.py) |
| AC-29 reject → audit DOCUMENT_REJECTED + analytics event | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `_emit_rejected` + `upload_errors_total{error_code}` | [test_upload_audit.py](../../tests/integration/test_upload_audit.py) + [test_upload_metrics.py](../../tests/integration/test_upload_metrics.py) |
| AC-30 metrics upload доступны | [observability/metrics.py](../../src/fe_bot/observability/metrics.py) `/metrics` endpoint | [test_upload_metrics.py](../../tests/integration/test_upload_metrics.py) |

## Implementation tasks → файлы → тесты

| Task | Файлы | Тесты |
|---|---|---|
| **T-S02-001** UploadBatchDTO | [schemas/setup/upload_batch.py](../../schemas/setup/upload_batch.py) | [test_upload_batch_schema.py](../../tests/unit/test_upload_batch_schema.py) |
| **T-S02-002** UploadErrorCode + UploadFileError | [schemas/setup/upload_errors.py](../../schemas/setup/upload_errors.py) | [test_upload_errors.py](../../tests/unit/test_upload_errors.py) |
| **T-S02-003** UploadDocumentsResponse v2 | [api/setup/dto.py](../../src/fe_bot/api/setup/dto.py) | [test_upload_response_dto.py](../../tests/unit/test_upload_response_dto.py) + [test_upload_response_contract.py](../../tests/contract/test_upload_response_contract.py) |
| **T-S02-004** Filename safety | [setup/upload/validation.py](../../src/fe_bot/setup/upload/validation.py) `_validate_filename_safety` | [test_upload_validation.py](../../tests/unit/test_upload_validation.py) `TestFilenameSafety` |
| **T-S02-005** Batch limits | `validation.py:validate_batch_limits` | [test_upload_batch_limits.py](../../tests/unit/test_upload_batch_limits.py) |
| **T-S02-006** Filename uniqueness | `validation.py:check_filename_uniqueness` | [test_upload_batch_validation.py](../../tests/integration/test_upload_batch_validation.py) |
| **T-S02-007** Idempotency cache | [setup/upload/idempotency.py](../../src/fe_bot/setup/upload/idempotency.py) | [test_idempotency_cache.py](../../tests/unit/test_idempotency_cache.py) + [test_upload_idempotency.py](../../tests/integration/test_upload_idempotency.py) |
| **T-S02-008** BatchRegistry | [setup/upload/batch_registry.py](../../src/fe_bot/setup/upload/batch_registry.py) | [test_batch_registry.py](../../tests/unit/test_batch_registry.py) |
| **T-S02-009** Router batch tracking | [api/setup/router.py](../../src/fe_bot/api/setup/router.py) `upload_documents` | [test_upload_batch_tracking.py](../../tests/integration/test_upload_batch_tracking.py) |
| **T-S02-010** Contract test | [test_upload_response_contract.py](../../tests/contract/test_upload_response_contract.py) | — |
| **T-S02-011** Audit hooks | `setup/upload/service.py` `_emit_*` | [test_upload_audit.py](../../tests/integration/test_upload_audit.py) |
| **T-S02-012** Metrics | `setup/upload/service.py` counters + histograms | [test_upload_metrics.py](../../tests/integration/test_upload_metrics.py) |
| **T-S02-013** Structured logging | `setup/upload/service.py` `logger.info(extra={...})` | [test_upload_logging.py](../../tests/unit/test_upload_logging.py) |
| **T-S02-014** DELETE endpoint | [api/setup/router.py](../../src/fe_bot/api/setup/router.py) `delete_document` + `service.remove_document` | [test_delete_document.py](../../tests/integration/test_delete_document.py) |
| **T-S02-015** GET document metadata | `router.py:get_document_metadata` | [test_get_document_metadata.py](../../tests/integration/test_get_document_metadata.py) |
| **T-S02-016** Retry endpoint | **DEFERRED → SETUP-03 / S5** | [test_no_retry_endpoint.py](../../tests/contract/test_no_retry_endpoint.py) (negative contract) |
| **T-S02-017** FileUploadPanel | [components/Upload/FileUploadPanel.tsx](../../frontend/src/components/Upload/FileUploadPanel.tsx) | [FileUploadPanel.test.tsx](../../frontend/src/components/Upload/__tests__/FileUploadPanel.test.tsx) |
| **T-S02-018** UploadProgressList + useUploadProgress | [Upload/UploadProgressList.tsx](../../frontend/src/components/Upload/UploadProgressList.tsx) + [hooks/useUploadProgress.ts](../../frontend/src/hooks/useUploadProgress.ts) | [UploadProgressList.test.tsx](../../frontend/src/components/Upload/__tests__/UploadProgressList.test.tsx) |
| **T-S02-019** Client validation lib | [lib/uploadValidation.ts](../../frontend/src/lib/uploadValidation.ts) | [uploadValidation.test.ts](../../frontend/src/lib/__tests__/uploadValidation.test.ts) |
| **T-S02-020** UploadedFilesTable | [Upload/UploadedFilesTable.tsx](../../frontend/src/components/Upload/UploadedFilesTable.tsx) | [UploadedFilesTable.test.tsx](../../frontend/src/components/Upload/__tests__/UploadedFilesTable.test.tsx) |
| **T-S02-021** FileValidationErrorsPanel | [Upload/FileValidationErrorsPanel.tsx](../../frontend/src/components/Upload/FileValidationErrorsPanel.tsx) | [FileValidationErrorsPanel.test.tsx](../../frontend/src/components/Upload/__tests__/FileValidationErrorsPanel.test.tsx) |
| **T-S02-022** DuplicateFileDialog | [Upload/DuplicateFileDialog.tsx](../../frontend/src/components/Upload/DuplicateFileDialog.tsx) | [DuplicateFileDialog.test.tsx](../../frontend/src/components/Upload/__tests__/DuplicateFileDialog.test.tsx) |
| **T-S02-023** Orphan cleanup | [setup/upload/cleanup.py](../../src/fe_bot/setup/upload/cleanup.py) + [api/admin/router.py](../../src/fe_bot/api/admin/router.py) | [test_orphan_cleanup.py](../../tests/integration/test_orphan_cleanup.py) |
| **T-S02-024** Resilience | — | [test_upload_resilience.py](../../tests/integration/test_upload_resilience.py) |
| **T-S02-025** Docs | этот файл + [SETUP-02.tasks.md](../implementation-plan/SETUP-02.tasks.md) | — |

## Events

| Event | Producer | Consumer | Tests |
|---|---|---|---|
| `DOCUMENT_UPLOADED` (audit) | DocumentUploadService | AuditService | test_upload_audit.py |
| `DOCUMENT_REJECTED` (audit) | DocumentUploadService | AuditService | test_upload_audit.py |
| `DOCUMENT_DUPLICATE_SKIPPED` (audit) | DocumentUploadService | AuditService | test_upload_audit.py |
| `DOCUMENT_REMOVED` (audit) | DocumentUploadService.remove_document | AuditService | test_delete_document.py |
| `BATCH_COMPLETED` (audit) | router.upload_documents | AuditService | test_upload_audit.py |
| `setup.document.uploaded` (EventBus / SSE) | DocumentUploadService | EventBus → SSE | test_sse_events.py |

## API endpoints

| Endpoint | Permission | Handler | Tests |
|---|---|---|---|
| POST `/setup/{id}/documents` | KB_DOCUMENT_UPLOAD | router.upload_documents | test_upload_documents.py, test_upload_batch_validation.py, test_upload_idempotency.py, test_upload_batch_tracking.py, test_upload_audit.py, test_upload_metrics.py, test_upload_resilience.py |
| GET `/setup/{id}/documents` | KB_DOCUMENT_UPLOAD | router.list_documents | test_upload_documents.py |
| GET `/setup/{id}/documents/{doc_id}` | KB_DOCUMENT_UPLOAD | router.get_document_metadata | test_get_document_metadata.py |
| DELETE `/setup/{id}/documents/{doc_id}` | KB_DOCUMENT_DELETE | router.delete_document | test_delete_document.py |
| POST `/admin/cleanup/orphans` | KB_ADMIN_CLEANUP | admin/router.cleanup_orphans | test_orphan_cleanup.py |

## Открытые вопросы из спецификации (§22.3)

| Вопрос | Решение MVP | Marker |
|---|---|---|
| MAX_FILE_SIZE_BYTES | 100 MB | [schemas/common/defaults.py](../../schemas/common/defaults.py) `MAX_FILE_SIZE_BYTES` |
| MAX_BATCH_FILES_COUNT | 50 | `defaults.py` `MAX_BATCH_FILES_COUNT` |
| MAX_TOTAL_BATCH_SIZE_BYTES | 500 MB | `defaults.py` `MAX_TOTAL_BATCH_SIZE_BYTES` |
| upload_as_new_version | Реализован в DocumentUploadService, скрыт за feature flag в UI | DuplicateFileDialog `enableUploadAsNewVersion` prop |
| Antivirus scanning | Не в MVP | — |
| Preview содержимого | Не в MVP | — |
| DMS integration | Не в MVP | — |
| TTL для removed files | TBD; в MVP остаются в registry с status=REMOVED | OrphanCleanupService `min_age` |
| Frontend checksum | Не считаем (нагрузка на browser); backend authoritative | — |

## Coverage summary

```
Backend tests       → 657 passed
Frontend tests      → 64 passed
Contract tests      → 2 (response + no-retry)
mypy --strict       → 0 errors (87 files)
ruff                → 0 errors
```
