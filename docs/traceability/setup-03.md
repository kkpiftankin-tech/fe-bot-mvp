# SETUP-03 Traceability Matrix

Связь каждого артефакта SETUP-03 «Source Registry» с implementation файлами
и тестами. Поддерживается в актуальном состоянии при изменении фичи.

**Спецификация:** [docs/02-system/features/SETUP-03-source-registry.md](../02-system/features/SETUP-03-source-registry.md) + приложенное детальное описание (23 секции, 34 AC).
**План:** [docs/implementation-plan/SETUP-03.tasks.md](../implementation-plan/SETUP-03.tasks.md)

## Acceptance Criteria → реализация → тест

### Регистрация источника (AC-01..05)

| AC | Реализация | Тест |
|---|---|---|
| AC-01 после upload создаётся SourceDocumentDTO | [src/fe_bot/setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `upload()` + `_lifecycle.update_status(REGISTERED)` | [test_upload_to_registry_flow.py](../../tests/integration/test_upload_to_registry_flow.py) |
| AC-02 DTO содержит все обязательные поля | [schemas/setup/source_document.py](../../schemas/setup/source_document.py) `SourceDocument` | [test_source_document_schema.py](../../tests/unit/test_source_document_schema.py) |
| AC-03 source_document_id неизменяемый | Pydantic frozen на model_copy + storage | test_source_document_schema.py |
| AC-04 checksum неизменяемый | [src/fe_bot/setup/source_registry/service.py](../../src/fe_bot/setup/source_registry/service.py) `update()` rejects checksum change | [test_source_registry.py](../../tests/unit/test_source_registry.py) |
| AC-05 начальный статус registered после T-S03-019 | [setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) auto-trigger update_status | test_upload_to_registry_flow.py |

### Список источников (AC-06..10)

| AC | Реализация | Тест |
|---|---|---|
| AC-06 KB_SOURCE_LIST даёт доступ | [auth/permissions.py](../../src/fe_bot/auth/permissions.py) + [sources_router.py](../../src/fe_bot/api/setup/sources_router.py) `list_sources` | [test_list_sources.py](../../tests/integration/test_list_sources.py) + [test_auth_permissions.py](../../tests/unit/test_auth_permissions.py) |
| AC-07 без permission → 403 | `require_permission(KB_SOURCE_LIST)` | test_list_sources.py `TestListSourcesAccessControl` |
| AC-08 pagination | `_paginate[T]` + PaginationDTO | test_list_sources.py `TestListSourcesPaginationAndSort` |
| AC-09 фильтр по status | status_filter query | test_list_sources.py `TestListSourcesFilters` |
| AC-10 counters в списке | `lineage.counters()` в `_build_list_item` | test_list_sources.py `test_list_item_has_counters` |

### Карточка документа (AC-11..16)

| AC | Реализация | Тест |
|---|---|---|
| AC-11 открыть детали | GET /sources/{id} → SourceDocumentDetailsDTO | [test_get_source_details.py](../../tests/integration/test_get_source_details.py) |
| AC-12 technical metadata | system_metadata в response | test_get_source_details.py |
| AC-13 user metadata | document.metadata["user"] → user_metadata | test_get_source_details.py + test_patch_source_metadata.py |
| AC-14 checksum | response.checksum (full sha256) | test_get_source_details.py |
| AC-15 владелец и uploaded_at | uploaded_by, uploaded_at | test_get_source_details.py |
| AC-16 current status | response.status | test_get_source_details.py |

### Status history и processing log (AC-17..20)

| AC | Реализация | Тест |
|---|---|---|
| AC-17 каждый transition → history entry | [lifecycle.py](../../src/fe_bot/setup/source_registry/lifecycle.py) `update_status` + [status_history.py](../../src/fe_bot/setup/source_registry/status_history.py) | [test_source_lifecycle_service.py](../../tests/unit/test_source_lifecycle_service.py) + [test_status_history_endpoint.py](../../tests/integration/test_status_history_endpoint.py) |
| AC-18 хронологический порядок | InMemoryStatusHistoryRepository — append-only | [test_status_history_repository.py](../../tests/unit/test_status_history_repository.py) |
| AC-19 processing log с timestamp | SourceProcessingLogEntry + lifecycle.append_processing_log | [test_processing_log_endpoint.py](../../tests/integration/test_processing_log_endpoint.py) |
| AC-20 ошибки → error_code в логе | append_processing_log с level=ERROR + error_code | test_processing_log_endpoint.py `test_filter_by_level_error` |

### Lineage (AC-21..24)

| AC | Реализация | Тест |
|---|---|---|
| AC-21 ссылки на parsed sections | [lineage.py](../../src/fe_bot/setup/source_registry/lineage.py) + `LineageTargetType.PARSED_SECTION` | [test_lineage_repository.py](../../tests/unit/test_lineage_repository.py) |
| AC-22 ссылки на RAG cards | `LineageTargetType.RAG_CARD` | test_lineage_repository.py + test_source_lifecycle_service.py |
| AC-23 lineage API возвращает counters | `LineageRepository.counters()` | test_processing_log_endpoint.py `TestLineageEndpoint` |
| AC-24 дубликат не создаётся | InMemoryLineageRepository `_by_unique_key` | test_lineage_repository.py `test_idempotent_by_unique_key` |

### Metadata update (AC-25..27)

| AC | Реализация | Тест |
|---|---|---|
| AC-25 PATCH tags/description | [sources_router.py](../../src/fe_bot/api/setup/sources_router.py) `patch_source_metadata` | [test_patch_source_metadata.py](../../tests/integration/test_patch_source_metadata.py) |
| AC-26 protected fields rejected | [source_document_metadata.py](../../schemas/setup/source_document_metadata.py) `PROTECTED_FIELDS` + `extra="forbid"` | [test_user_metadata_schema.py](../../tests/unit/test_user_metadata_schema.py) + test_patch_source_metadata.py |
| AC-27 audit event при PATCH | [audit/service.py](../../src/fe_bot/audit/service.py) `METADATA_UPDATED` + lifecycle `_audit_record` | [test_source_audit_metrics.py](../../tests/integration/test_source_audit_metrics.py) |

### Удаление (AC-28..30)

| AC | Реализация | Тест |
|---|---|---|
| AC-28 user может удалить до pipeline | DELETE /sources/{id} + KB_SOURCE_REMOVE | [test_delete_source.py](../../tests/integration/test_delete_source.py) |
| AC-29 published блокирует удаление без admin | `sources_router.py` `if status == PUBLISHED and not KB_PUBLISH` → 409 | test_delete_source.py `TestDeletePublishedProtection` |
| AC-30 soft-delete (status=removed) | [source_registry/service.py](../../src/fe_bot/setup/source_registry/service.py) `remove()` | test_delete_source.py + test_source_registry.py |

### События и аудит (AC-31..34)

| AC | Реализация | Тест |
|---|---|---|
| AC-31 source.document.registered | lifecycle.update_status → _publish("source.document.registered") | [test_source_events.py](../../tests/integration/test_source_events.py) |
| AC-32 source.document.status_changed | _publish для не-REGISTERED transitions | test_source_events.py + [test_source_audit_metrics.py](../../tests/integration/test_source_audit_metrics.py) |
| AC-33 source.document.metadata_updated | _publish из update_user_metadata | test_source_events.py |
| AC-34 audit trail для всех значимых действий | AuditService + STATUS_CHANGED/METADATA_UPDATED/LINEAGE_ADDED/PROCESSING_RETRY_TRIGGERED | test_source_audit_metrics.py |

## Implementation tasks → файлы → тесты

| Task | Файлы | Тесты |
|---|---|---|
| **T-S03-001** Status enum (+13) | [schemas/setup/source_document.py](../../schemas/setup/source_document.py) | [test_source_document_schema.py](../../tests/unit/test_source_document_schema.py) |
| **T-S03-002** StatusHistory DTO + state machine | [schemas/setup/status_history.py](../../schemas/setup/status_history.py) | [test_status_history_schema.py](../../tests/unit/test_status_history_schema.py) |
| **T-S03-003** ProcessingLog DTO | [schemas/setup/processing_log.py](../../schemas/setup/processing_log.py) | [test_processing_log_schema.py](../../tests/unit/test_processing_log_schema.py) |
| **T-S03-004** Lineage DTO | [schemas/setup/lineage.py](../../schemas/setup/lineage.py) | [test_lineage_schema.py](../../tests/unit/test_lineage_schema.py) |
| **T-S03-005** UserMetadata DTO + sanitization | [schemas/setup/source_document_metadata.py](../../schemas/setup/source_document_metadata.py) | [test_user_metadata_schema.py](../../tests/unit/test_user_metadata_schema.py) |
| **T-S03-006** StatusHistoryRepository | [src/fe_bot/setup/source_registry/status_history.py](../../src/fe_bot/setup/source_registry/status_history.py) | [test_status_history_repository.py](../../tests/unit/test_status_history_repository.py) |
| **T-S03-007** ProcessingLogRepository | [src/fe_bot/setup/source_registry/processing_log.py](../../src/fe_bot/setup/source_registry/processing_log.py) | [test_processing_log_repository.py](../../tests/unit/test_processing_log_repository.py) |
| **T-S03-008** LineageRepository | [src/fe_bot/setup/source_registry/lineage.py](../../src/fe_bot/setup/source_registry/lineage.py) | [test_lineage_repository.py](../../tests/unit/test_lineage_repository.py) |
| **T-S03-009** SourceLifecycleService.update_status | [src/fe_bot/setup/source_registry/lifecycle.py](../../src/fe_bot/setup/source_registry/lifecycle.py) | [test_source_lifecycle_service.py](../../tests/unit/test_source_lifecycle_service.py) `TestUpdateStatus` |
| **T-S03-010** append_log + link_artifact + get_lineage | `lifecycle.py` | test_source_lifecycle_service.py `TestProcessingLog/TestLinkArtifact/TestGetLineage` |
| **T-S03-011** update_user_metadata | `lifecycle.py` | test_source_lifecycle_service.py `TestUpdateUserMetadata` |
| **T-S03-012** GET /sources | [src/fe_bot/api/setup/sources_router.py](../../src/fe_bot/api/setup/sources_router.py) + [sources_dto.py](../../src/fe_bot/api/setup/sources_dto.py) | [test_list_sources.py](../../tests/integration/test_list_sources.py) |
| **T-S03-013** GET /sources/{id} | sources_router.py `get_source_details` | [test_get_source_details.py](../../tests/integration/test_get_source_details.py) |
| **T-S03-014** GET /status-history | sources_router.py `get_status_history` | [test_status_history_endpoint.py](../../tests/integration/test_status_history_endpoint.py) |
| **T-S03-015** GET /processing-log + /lineage | sources_router.py `get_processing_log` + `get_lineage` | [test_processing_log_endpoint.py](../../tests/integration/test_processing_log_endpoint.py) |
| **T-S03-016** kb.source.* permissions | [src/fe_bot/auth/permissions.py](../../src/fe_bot/auth/permissions.py) (+6 permissions) | [test_auth_permissions.py](../../tests/unit/test_auth_permissions.py) |
| **T-S03-017** PATCH /metadata | sources_router.py `patch_source_metadata` | [test_patch_source_metadata.py](../../tests/integration/test_patch_source_metadata.py) |
| **T-S03-018** DELETE /sources/{id} | sources_router.py `delete_source` + published-блок | [test_delete_source.py](../../tests/integration/test_delete_source.py) |
| **T-S03-019** Upload → Registry integration | [src/fe_bot/setup/upload/service.py](../../src/fe_bot/setup/upload/service.py) `_lifecycle` injection | [test_upload_to_registry_flow.py](../../tests/integration/test_upload_to_registry_flow.py) |
| **T-S03-020** source.document.* events | `lifecycle.py` `_publish()` | [test_source_events.py](../../tests/integration/test_source_events.py) |
| **T-S03-021** POST /retry | sources_router.py `retry_source` + `lifecycle.retry_processing` | [test_source_retry.py](../../tests/integration/test_source_retry.py) |
| **T-S03-022** Audit + metrics | [src/fe_bot/audit/service.py](../../src/fe_bot/audit/service.py) (+4 actions) + lifecycle `_audit_record`/`_inc` | [test_source_audit_metrics.py](../../tests/integration/test_source_audit_metrics.py) |
| **T-S03-023** API client + types | [frontend/src/api/types.ts](../../frontend/src/api/types.ts) + [sources.ts](../../frontend/src/api/sources.ts) + 8 MSW handlers | покрыто компонентами |
| **T-S03-024** SourceRegistryTab + Table | [frontend/src/components/SourceRegistry/SourceRegistryTab.tsx](../../frontend/src/components/SourceRegistry/SourceRegistryTab.tsx) + [SourceDocumentTable.tsx](../../frontend/src/components/SourceRegistry/SourceDocumentTable.tsx) | [SourceDocumentTable.test.tsx](../../frontend/src/components/SourceRegistry/__tests__/SourceDocumentTable.test.tsx) + [SourceRegistryTab.test.tsx](../../frontend/src/components/SourceRegistry/__tests__/SourceRegistryTab.test.tsx) |
| **T-S03-025** DetailsDrawer (5 tabs) | [SourceDocumentDetailsDrawer.tsx](../../frontend/src/components/SourceRegistry/SourceDocumentDetailsDrawer.tsx) | [SourceDocumentDetailsDrawer.test.tsx](../../frontend/src/components/SourceRegistry/__tests__/SourceDocumentDetailsDrawer.test.tsx) |
| **T-S03-026** MetadataEditor | [MetadataEditor.tsx](../../frontend/src/components/SourceRegistry/MetadataEditor.tsx) | [MetadataEditor.test.tsx](../../frontend/src/components/SourceRegistry/__tests__/MetadataEditor.test.tsx) |
| **T-S03-027** Resilience tests | [test_source_registry_resilience.py](../../tests/integration/test_source_registry_resilience.py) | — |
| **T-S03-028** Documentation | этот файл | — |
| **T-S03-029** Final verify | — | full gate |

## Endpoints

| Endpoint | Permission | Handler | Tests |
|---|---|---|---|
| GET `/setup/{sid}/sources` | KB_SOURCE_LIST | sources_router.list_sources | test_list_sources.py |
| GET `/setup/{sid}/sources/{id}` | KB_SOURCE_READ | sources_router.get_source_details | test_get_source_details.py |
| GET `/setup/{sid}/sources/{id}/status-history` | KB_SOURCE_READ | sources_router.get_status_history | test_status_history_endpoint.py |
| GET `/setup/{sid}/sources/{id}/processing-log` | KB_SOURCE_LOG_READ | sources_router.get_processing_log | test_processing_log_endpoint.py |
| GET `/setup/{sid}/sources/{id}/lineage` | KB_SOURCE_LINEAGE_READ | sources_router.get_lineage | test_processing_log_endpoint.py `TestLineageEndpoint` |
| PATCH `/setup/{sid}/sources/{id}/metadata` | KB_SOURCE_METADATA_UPDATE | sources_router.patch_source_metadata | test_patch_source_metadata.py |
| DELETE `/setup/{sid}/sources/{id}` | KB_SOURCE_REMOVE | sources_router.delete_source | test_delete_source.py |
| POST `/setup/{sid}/sources/{id}/retry` | KB_SETUP_RUN | sources_router.retry_source | test_source_retry.py |

## Events (T-S03-020)

| Event | Producer | Trigger | Tests |
|---|---|---|---|
| `source.document.registered` | lifecycle._publish | update_status → REGISTERED | test_source_events.py `TestRegisteredEvent` |
| `source.document.status_changed` | lifecycle._publish | update_status → any non-REGISTERED | test_source_events.py `TestStatusChangedEvent` |
| `source.document.metadata_updated` | lifecycle._publish | update_user_metadata | test_source_events.py `TestMetadataUpdatedEvent` |
| `source.document.lineage_updated` | lifecycle._publish | link_artifact (new link) | test_source_events.py `TestLineageUpdatedEvent` |
| `source.document.processing_failed` | lifecycle._publish | append_processing_log(level=ERROR, new entry) | test_source_events.py `TestProcessingFailedEvent` |

## Audit actions (T-S03-022)

| AuditAction | Trigger | Tests |
|---|---|---|
| `STATUS_CHANGED` | update_status (actual change) | test_source_audit_metrics.py `TestStatusChangedAudit` |
| `METADATA_UPDATED` | update_user_metadata | test_source_audit_metrics.py `TestMetadataUpdatedAudit` |
| `LINEAGE_ADDED` | link_artifact (new link) | test_source_audit_metrics.py `TestLineageAddedAuditAndMetrics` |
| `PROCESSING_RETRY_TRIGGERED` | retry_processing | test_source_audit_metrics.py `TestRetryAudit` |

## Metrics (T-S03-022)

| Metric | Labels | Trigger |
|---|---|---|
| `source_status_changes_total` | from_status, to_status | каждый успешный update_status (actual change) |
| `source_documents_total` | status | cumulative on transition |
| `source_processing_failures_total` | step, error_code | append_processing_log(ERROR, new entry) |
| `source_lineage_relations_total` | target_type, relation_type | link_artifact (new link) |

## Открытые вопросы из спецификации §22.3

| Вопрос | Решение MVP | Marker |
|---|---|---|
| Версионирование source documents | Отложено — single version per checksum | future_field `parent_source_document_id` зарезервирован |
| Удаление документа после parsed sections, до RAG cards | Разрешено (см. state machine `PARSED` → `REMOVED`) | [status_history.py](../../schemas/setup/status_history.py) `ALLOWED_TRANSITIONS[PARSED]` |
| Download/preview исходного файла | Не в MVP — `storage_path` masked для не-admin | [sources_router.py](../../src/fe_bot/api/setup/sources_router.py) `include_paths` |
| Retention policy processing log | Не в MVP — append-only без cleanup | future INF |
| document_kind вручную редактируемый | Не в MVP — только через автодетект (future) | — |
| Обязательные статусы MVP | uploaded, registered, parsing, parsed, rag_cards_generated, review_required, published, removed, parse_failed, processing_failed (10/20) | enum в SourceDocumentStatus |
| Отдельная роль auditor | Реализована: read-only `kb.source.*` + `kb.report.read` | [auth/permissions.py](../../src/fe_bot/auth/permissions.py) |
| Lineage для большого числа RAG-карточек | Counters + relations с pagination + reverse lookup | [lineage.py](../../src/fe_bot/setup/source_registry/lineage.py) |

## Coverage summary

```
Backend tests       → 859 passed
Frontend tests      → 85 passed
mypy --strict       → 0 errors (97 files)
ruff                → 0 errors
```

## Зависимости и интеграция

- **SETUP-02** (upload) intercept'ит результат `_registry.add()` через SourceLifecycleService → auto REGISTERED status + UPLOAD log entry.
- **SETUP-04** (parsing) — будет использовать `update_status(PARSING/PARSED)` + `link_artifact(PARSED_SECTION)`.
- **SETUP-05** (RAG cards) — `link_artifact(RAG_CARD, GENERATED_FROM)`.
- **SETUP-11** (Knowledge Base) — `update_status(PUBLISHED)` + `link_artifact(KNOWLEDGE_BASE_VERSION, INCLUDED_IN)`.
- **INF-002** (PostgreSQL migration) — все 4 in-memory repositories заменятся на SQLAlchemy + unique constraints.
- **INF-005** (Kafka) — EventBus заменится на Kafka producer; `event_type` префиксы `source.document.*` останутся.
