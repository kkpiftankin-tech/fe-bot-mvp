# SETUP-06 — Implementation plan

Реализация SETUP-06 «Просмотр, редактирование и подтверждение RAG-карточек» по слайсам S0..S7. Основной источник требований: [docs/02-system/features/SETUP-06-rag-card-review.md](../02-system/features/SETUP-06-rag-card-review.md).

## Контекст и зависимости

- **Вход:** SETUP-05 завершён — карточки в статусах `generated`, `review_required`, `low_confidence`, `metadata_incomplete`, `validation_failed`. Существует `RAGCardGenerationOrchestrator` для regenerate.
- **Выход:** карточки в статусах `approved`/`rejected`/`regenerate_requested`, готовые к SETUP-07 (metadata validation) и SETUP-08 (chunking).
- **Существующий MVP-каркас:** `RAGCardReviewService` ([src/fe_bot/setup/card_review/service.py](../../src/fe_bot/setup/card_review/service.py), 245 строк) + endpoint `/rag-cards/{doc_id}/review` ([src/fe_bot/api/setup/router.py:798](../../src/fe_bot/api/setup/router.py#L798)) + 167-строчный тест. **Будет существенно переработан**, а не дополнен.

## Метрики плана

- **40 задач** в 8 слайсах + 4 design-артефакта в Phase A (часть уже есть в feature spec).
- **~200 новых тестов** (unit + component + integration + frontend).
- **2 промежуточных commit** (после S3 backend и после S5 frontend).
- **Зависимости от SETUP-05:** `RAGCardGenerationOrchestrator.create_job()`, `card_version` policy, `CardStatus` extension.
- **Зависимости от SETUP-04/03:** `ParsedSection`, `SourceLifecycleService`.
- **Зависимости от SETUP-01:** `AuditService`, `EventBus`, `MetricsRegistry`, `ArtifactStorage`, `Permission`.

---

## Phase A. Design (4 артефакта)

### A1. Feature spec — done

Полный 23-секционный документ: [docs/02-system/features/SETUP-06-rag-card-review.md](../02-system/features/SETUP-06-rag-card-review.md).

### A2. DTO catalog update

Target: `docs/03-architecture/services/data-transfer-objects.md` (расширить DTO-67..78).

Acceptance:
- Новые DTO: `ReviewDecisionDTO` (DTO-67), `ReviewLogDTO` (DTO-68), `RAGCardVersionDTO` (DTO-69), `RAGCardDiffDTO` (DTO-70), `RAGCardValidationSnapshotDTO` (DTO-71), `RAGCardEditLockDTO` (DTO-72), `ReviewRAGCardRequest` (DTO-73), `EditRAGCardRequest` (DTO-74), `RegenerateRAGCardReviewRequest` (DTO-75), `BulkReviewRequest` (DTO-76), `RAGCardReviewListItemDTO` (DTO-77), `RAGCardReviewDetailsDTO` (DTO-78).
- Для каждого DTO: storage mapping (in-memory MVP), producer SVC, consumer SVC.

### A3. Card lifecycle update

Target: `docs/06-rag/card-lifecycle.md` (расширить секцию переходов).

Acceptance:
- Полный state machine для review flow: `generated/review_required/metadata_incomplete/validation_failed → approved/rejected/edited/regenerate_requested`.
- Versioning policy: edit создаёт новую `card_version`; rejected версия не удаляется; approved версия фиксируется как `is_current`.
- Edit lock TTL и policy.

### A4. Test plan

Target: `docs/10-testing/SETUP-06-test-plan.md` (новый).

Acceptance:
- AC-01..AC-46 → тесты (минимум 1 тест на AC).
- Test pyramid: ~120 unit, ~30 component, ~40 integration, ~10 frontend, ~10 negative.
- Прометей-метрики и audit actions покрыты тестами.

---

## S0. Schemas (T-S06-001..006)

### T-S06-001. ReviewDecisionDTO + ReviewDecision enum

Target:
- `schemas/setup/review_decision.py` (новый)
- `tests/unit/test_review_decision_schema.py`

Acceptance:
- `ReviewDecision` enum: APPROVE, REJECT, EDIT, REGENERATE, SAVE_DRAFT, SUBMIT_EDIT, REQUEST_CHANGES, DEFER.
- `RejectReason` enum: DUPLICATE, WRONG_DOC_TYPE, INCORRECT_CONTENT, IRRELEVANT, HALLUCINATION, SOURCE_MISMATCH, OTHER.
- `ReviewDecisionDTO` (frozen=True): review_decision_id, setup_job_id, doc_id, card_version, decision, reason (Optional[RejectReason | str]), comment, reviewer_id, reviewer_role, created_at, metadata (dict).
- 12 unit-тестов: enum coverage, frozen, validation errors.

### T-S06-002. ReviewLogDTO + ReviewLogEventType

Target:
- `schemas/setup/review_log.py`
- `tests/unit/test_review_log_schema.py`

Acceptance:
- `ReviewLogEventType` enum: REVIEW_STARTED, APPROVED, REJECTED, EDITED, REGENERATE_REQUESTED, VERSION_CREATED, REVIEW_COMPLETED, EDIT_LOCK_ACQUIRED, EDIT_LOCK_RELEASED.
- `ReviewLogDTO` (frozen=True): review_log_id, setup_job_id, doc_id, card_version, event_type, actor_id, actor_role, message, before_status, after_status, created_at, payload.
- 10 unit-тестов.

### T-S06-003. RAGCardVersionDTO

Target:
- `schemas/setup/rag_card_version.py`
- `tests/unit/test_rag_card_version_schema.py`

Acceptance:
- `RAGCardVersionDTO` (frozen=True): doc_id, card_version, parent_card_version, status (CardStatus), markdown_artifact_id, metadata_snapshot, body_hash (sha256), created_by, created_at, change_reason, is_current.
- `bump_version()` helper: "1.0" → "1.1", "1.5" → "1.6"; minor bump для edit; major bump для regenerate.
- 8 unit-тестов: bump, hash, is_current invariant.

### T-S06-004. RAGCardDiffDTO + MetadataFieldDiff

Target:
- `schemas/setup/rag_card_diff.py`
- `tests/unit/test_rag_card_diff_schema.py`

Acceptance:
- `MetadataFieldDiff`: field, old_value, new_value.
- `BodyDiff`: format (Literal["unified"]), content.
- `RAGCardDiffDTO`: doc_id, from_version, to_version, metadata_diff (list), body_diff (Optional).
- 6 unit-тестов.

### T-S06-005. RAGCardEditLockDTO + EditLockStatus

Target:
- `schemas/setup/rag_card_edit_lock.py`
- `tests/unit/test_rag_card_edit_lock_schema.py`

Acceptance:
- `EditLockStatus` enum: ACTIVE, RELEASED, EXPIRED.
- `RAGCardEditLockDTO`: lock_id, doc_id, card_version, locked_by, locked_at, expires_at, status.
- `is_expired(now)` method.
- 6 unit-тестов.

### T-S06-006. Расширение CardStatus

Target:
- `schemas/rag/rag_card.py` (extend)
- `tests/unit/test_rag_card_status_setup06.py`

Acceptance:
- Новые статусы (если ещё не было): `EDITING`, `EDITED`, `REGENERATE_REQUESTED`, `VALIDATION_FAILED`.
- State machine: переходы из feature §12 (generated/review_required/... → approved/rejected/edited/regenerate_requested).
- 14 unit-тестов: все переходы из §12.

**Gate S0:** ~56 unit-тестов зелёные, mypy clean.

---

## S1. Repositories (T-S06-007..011)

### T-S06-007. InMemoryReviewDecisionRepository

Target:
- `src/fe_bot/setup/card_review/decision_repository.py`
- `tests/unit/test_review_decision_repository.py`

Acceptance:
- Protocol + impl: `add`, `get`, `list_for_card(doc_id)`, `list_for_setup_job(setup_job_id)`, `list_for_reviewer(reviewer_id)`, `exists(review_decision_id)`.
- Идемпотентность по `review_decision_id`: повторный `add` с тем же id — no-op + возврат существующего.
- Thread-safe (threading.Lock + deep-copy).
- 10 unit-тестов.

### T-S06-008. InMemoryReviewLogRepository

Target:
- `src/fe_bot/setup/card_review/log_repository.py`
- `tests/unit/test_review_log_repository.py`

Acceptance:
- Append-only: `append`, `list_for_card(doc_id, *, limit)`, `list_for_setup_job`, `count_for_card`.
- Chronological order при list.
- 8 unit-тестов.

### T-S06-009. InMemoryRAGCardVersionRepository

Target:
- `src/fe_bot/setup/card_review/version_repository.py`
- `tests/unit/test_rag_card_version_repository.py`

Acceptance:
- `add(version)`, `get(doc_id, card_version)`, `list_for_card(doc_id)`, `current(doc_id)`, `set_current(doc_id, card_version)`, `mark_deprecated(doc_id, card_version)`.
- Unique constraint (doc_id, card_version).
- Только одна версия с `is_current=True` per doc_id.
- 12 unit-тестов.

### T-S06-010. InMemoryEditLockRepository

Target:
- `src/fe_bot/setup/card_review/edit_lock_repository.py`
- `tests/unit/test_edit_lock_repository.py`

Acceptance:
- `acquire(doc_id, locked_by, ttl_seconds)` → returns lock or raises `EditLockActiveError(active_lock)`.
- `release(lock_id, released_by)` (только владелец или admin).
- `get_active(doc_id)`.
- `cleanup_expired(now)` → returns list of released expired locks.
- 10 unit-тестов: acquire happy, double-acquire conflict, expire, release, admin override.

### T-S06-011. SnapshotPersister extension

Target:
- `src/fe_bot/persistence/snapshot.py` (extend)
- `tests/unit/test_setup06_snapshot_persistence.py`

Acceptance:
- 4 новых репо включены в snapshot/restore.
- Round-trip тест.
- 5 unit-тестов.

**Gate S1:** ~45 unit-тестов зелёные.

---

## S2. Validators + Editor + Versioning (T-S06-012..018)

### T-S06-012. CardSourceTraceValidator

Target:
- `src/fe_bot/setup/card_review/validators/source_trace.py`
- `tests/unit/test_source_trace_validator.py`

Acceptance:
- `validate(card, source_section_repo, source_registry)` → `ValidationResult(passed, errors)`.
- Errors: `SOURCE_TRACE_REQUIRED` (no source_section_id), `SOURCE_DOCUMENT_NOT_FOUND`, `SOURCE_SECTION_NOT_FOUND`.
- 8 unit-тестов.

### T-S06-013. CardBodyValidator

Target:
- `src/fe_bot/setup/card_review/validators/body.py`
- `tests/unit/test_card_body_validator.py`

Acceptance:
- `validate(card)` — body не пустой, не короче 20 символов, нет dangerous HTML.
- Errors: `CARD_BODY_EMPTY`, `CARD_BODY_TOO_SHORT`, `CARD_BODY_DANGEROUS_HTML`.
- 8 unit-тестов.

### T-S06-014. PreApproveValidationOrchestrator

Target:
- `src/fe_bot/setup/card_review/validators/pre_approve.py`
- `tests/unit/test_pre_approve_validation.py`

Acceptance:
- Объединяет CardSourceTraceValidator + CardBodyValidator + metadata precheck из SETUP-05.
- Возвращает `PreApproveReport(passed, critical_errors, warnings)`.
- 12 unit-тестов: каждый блокирующий error отдельно.

### T-S06-015. CardEditorService

Target:
- `src/fe_bot/setup/card_review/editor.py`
- `tests/unit/test_card_editor_service.py`

Acceptance:
- `EDITABLE_METADATA_FIELDS` allowlist: title, retrieval_tags, domain, task_type, data_source, entity_type, phase, agent_targets, required_input_fields, output_fields, feature_tables, validation_rules, compatible_models.
- `apply_patch(card, metadata_patch, body_markdown)` → returns new card draft.
- Отклоняет system metadata fields → `SystemMetadataReadOnlyError`.
- `calculate_diff(old, new)` → RAGCardDiffDTO (unified body diff).
- 15 unit-тестов.

### T-S06-016. VersioningService

Target:
- `src/fe_bot/setup/card_review/versioning.py`
- `tests/unit/test_versioning_service.py`

Acceptance:
- `create_new_version(old_card, *, change_reason, created_by, body_markdown, metadata_snapshot)` → возвращает RAGCardVersionDTO + новую RAGCard.
- Bump policy: edit → minor (`1.0 → 1.1`), regenerate → major (`1.0 → 2.0`).
- `set_current_version(doc_id, card_version)` — атомарный switch.
- 10 unit-тестов.

### T-S06-017. ReviewReadinessCalculator

Target:
- `src/fe_bot/setup/card_review/readiness.py`
- `tests/unit/test_review_readiness.py`

Acceptance:
- `calculate(setup_job_id)` → `ReadinessSummary(total, approved, rejected, review_required, validation_failed, ready_for_next_step)`.
- `ready_for_next_step = (review_required == 0 and validation_failed == 0)`.
- 8 unit-тестов.

### T-S06-018. ReviewMetricsCollector

Target:
- `src/fe_bot/setup/card_review/metrics.py`
- `tests/unit/test_review_metrics_collector.py`

Acceptance:
- Counters: `rag_card_reviews_total{decision}`, `rag_card_approved_total{doc_type}`, `rag_card_rejected_total{reason}`, `rag_card_edited_total`, `rag_card_regenerate_requested_total`, `rag_card_validation_blocked_approve_total`, `rag_card_version_conflicts_total`.
- Histogram: `rag_card_review_duration_ms{decision,doc_type}`.
- 6 unit-тестов.

**Gate S2:** ~67 unit-тестов зелёные.

---

## S3. RAGCardReviewService rewrite + events (T-S06-019..023)

### T-S06-019. Events (8 типов)

Target:
- `src/fe_bot/setup/card_review/events.py`
- `tests/unit/test_review_events.py`

Acceptance:
- 8 событий (frozen=True): `RAGCardReviewStartedEvent`, `RAGCardApprovedEvent`, `RAGCardRejectedEvent`, `RAGCardEditedEvent`, `RAGCardVersionCreatedEvent`, `RAGCardRegenerateRequestedEvent`, `RAGCardReviewCompletedEvent`, `SetupReviewReadinessChangedEvent`.
- 8 unit-тестов.

### T-S06-020. RAGCardReviewService (rewrite)

Target:
- `src/fe_bot/setup/card_review/service.py` (rewrite)
- `tests/component/test_rag_card_review_service.py`

Acceptance: см. §11.1 feature spec — 12 use cases. Сервис принимает:
- `decision_repo`, `log_repo`, `version_repo`, `edit_lock_repo`, `card_registry`, `source_link_repo`, `parsed_section_repo`, `pre_approve_validator`, `card_editor`, `versioning`, `readiness_calculator`, `event_bus`, `audit_service`, `metrics`, `generation_orchestrator` (для regenerate).

Методы:
- `list_review_cards(setup_job_id, filters, pagination)`.
- `get_card_for_review(doc_id)` → `RAGCardReviewDetailsDTO`.
- `approve(doc_id, *, reviewer_id, review_decision_id, comment)`.
- `reject(doc_id, *, reviewer_id, reason, comment)`.
- `edit(doc_id, *, reviewer_id, expected_version, metadata_patch, body_markdown, change_reason)`.
- `request_regeneration(doc_id, *, reviewer_id, reason, regenerate_request_id)`.
- `bulk_approve(setup_job_id, *, reviewer_id, items, comment)`.
- `get_review_log(doc_id, *, pagination)`.
- `get_card_diff(doc_id, from_version, to_version)`.
- `get_card_versions(doc_id)`.

25 component-тестов: happy + edge + integration с registry + audit + metrics.

### T-S06-021. Integration с SETUP-05 RAGCardGenerationOrchestrator

Target:
- `src/fe_bot/setup/card_review/service.py` (regenerate flow)
- `tests/component/test_review_regenerate_integration.py`

Acceptance:
- `request_regeneration()` вызывает `rag_orchestrator.create_job(setup_job_id, requested_by, section_ids=[primary_section], config={"regenerate_of": doc_id, "reason": reason, "regenerate_request_id": request_id})`.
- Status карточки → `REGENERATE_REQUESTED`.
- Event `RAGCardRegenerateRequestedEvent` публикуется.
- Audit `RAG_CARD_REGENERATE_TRIGGERED`.
- 6 component-тестов.

### T-S06-022. Setup Orchestrator readiness recalculation

Target:
- `src/fe_bot/setup/orchestrator.py` (extend)
- `src/fe_bot/setup/card_review/service.py` (вызов после каждого decision)
- `tests/integration/test_setup_review_readiness.py`

Acceptance:
- После approve/reject/edit/regenerate → `readiness_calculator.calculate()` → если `ready_for_next_step` изменилось, публикуется `SetupReviewReadinessChangedEvent`.
- 8 integration-тестов.

### T-S06-023. DI wiring

Target:
- `src/fe_bot/api/dependencies.py` (extend)
- `src/fe_bot/app.py` (если нужны новые routers)

Acceptance:
- 4 новых singleton (decision/log/version/edit_lock repo), CardEditorService, VersioningService, ReadinessCalculator, новый RAGCardReviewService.
- Все get_*() функции.
- Snapshot persistence wired.

**Gate S3:** ~67 component-тестов зелёные + S0/S1/S2 не сломаны. Промежуточный commit.

---

## S4. API + RBAC (T-S06-024..028)

### T-S06-024. Permissions

Target:
- `src/fe_bot/auth/permissions.py` (extend)
- `tests/unit/test_setup06_permissions.py`

Acceptance:
- Новые permissions (12 штук из §5.3): `KB_RAG_CARD_LIST`, `KB_RAG_CARD_PREVIEW` (уже есть?), `KB_RAG_CARD_EDIT`, `KB_RAG_CARD_APPROVE`, `KB_RAG_CARD_REJECT`, `KB_RAG_CARD_REGENERATE` (уже есть), `KB_RAG_CARD_VERSION_READ`, `KB_RAG_CARD_DIFF_READ`, `KB_RAG_CARD_REVIEW_LOG_READ`, `KB_RAG_CARD_VALIDATION_READ`, `KB_RAG_CARD_SOURCE_TRACE_READ`, `KB_RAG_CARD_BULK_REVIEW`.
- Role matrix: USER (read+approve+reject+edit+regenerate), DOMAIN_EXPERT (то же), RAG_ADMIN (всё + bulk), AUDITOR (read-only + log), ADMIN (всё).
- 14 unit-тестов.

### T-S06-025. API DTO

Target:
- `src/fe_bot/api/setup/review_dto.py` (новый)

Acceptance:
- Все DTO из §15: `ReviewRAGCardRequest`, `EditRAGCardRequest`, `RegenerateRAGCardReviewRequest`, `BulkReviewRequest`, `RAGCardReviewListResponse`, `RAGCardReviewListItemDTO`, `RAGCardReviewDetailsDTO`, `ApproveResponse`, `EditResponse`, `RejectResponse`, `RegenerateResponse`, `BulkReviewResponse`, `RAGCardVersionsResponse`, `RAGCardDiffResponse`, `ReviewLogResponse`.
- Pydantic 2, ConfigDict(extra="forbid").

### T-S06-026. Review router (9 endpoints)

Target:
- `src/fe_bot/api/setup/review_router.py` (новый)
- `tests/integration/test_review_endpoints.py`

Acceptance: 9 endpoints (см. §16.1):
- GET `/rag-cards-review` (list)
- GET `/rag-cards-review/{doc_id}` (details)
- GET `/rag-cards-review/{doc_id}/versions`
- GET `/rag-cards-review/{doc_id}/diff?from_version=&to_version=`
- GET `/rag-cards-review/{doc_id}/review-log`
- POST `/rag-cards-review/{doc_id}/review` (approve/reject)
- PATCH `/rag-cards-review/{doc_id}` (edit)
- POST `/rag-cards-review/{doc_id}/regenerate`
- POST `/rag-cards-review/bulk-review`

Каждый endpoint: проверка `setup_job` ownership, RBAC, cross-job isolation (404), error mapping. 30 integration-тестов.

### T-S06-027. Deprecate legacy review endpoint

Target:
- `src/fe_bot/api/setup/router.py` — пометить `/rag-cards/{doc_id}/review` как deprecated (но оставить для backward compat).
- Update OpenAPI summary с deprecation notice.

Acceptance:
- Endpoint работает, но возвращает header `Deprecation: true`.
- Существующие 8 тестов в `test_review_card_endpoint.py` остаются зелёными.

### T-S06-028. App wiring

Target:
- `src/fe_bot/app.py` (include review_router)

Acceptance:
- `app.include_router(review_router)`.
- Healthcheck endpoint видит новый router.

**Gate S4:** ~52 integration-тестов зелёные.

---

## S5. Frontend (T-S06-029..036)

### T-S06-029. API client + types

Target:
- `frontend/src/api/review.ts` (новый)
- `frontend/src/api/types.ts` (extend)

Acceptance:
- 9 функций: `listReviewCards`, `getReviewCard`, `getReviewVersions`, `getReviewDiff`, `getReviewLog`, `reviewCard` (approve/reject), `editCard`, `regenerateCardForReview`, `bulkReview`.
- TypeScript types для всех DTO из §15.

### T-S06-030. WizardStore extension

Target:
- `frontend/src/store/wizardStore.ts` (extend)
- `frontend/src/components/Wizard/WizardLayout.tsx` (extend)

Acceptance:
- Текущий шаг `review` (`6. Проверить карточки`) переименовать в `review` с новой реализацией (или оставить как есть — старая `ReviewCardsStep` для legacy).
- Новый WizardStep — `card_review` между `rag_card_generation` и старым `review` (или заменить).
- Persist `reviewCardId` (selected card).

### T-S06-031. ReviewCardsStep (новый)

Target:
- `frontend/src/components/Wizard/steps/CardReviewStep.tsx` (новый)

Acceptance:
- Counter «Требуется review: N» + переход к подсветке.
- Embedded `RAGCardReviewTable` + `RAGCardPreviewDrawer`.
- Indicator readiness ⟶ возможность нажать «Далее» только если все обработаны.

### T-S06-032. RAGCardReviewTable

Target:
- `frontend/src/components/Wizard/review/RAGCardReviewTable.tsx`

Acceptance:
- Колонки: doc_id, title, doc_type, status, confidence, validation_errors_count, source_document, updated_at, actions.
- Фильтры: doc_type, status, confidence, has_validation_errors, source_document.
- Pagination.
- Quick actions: Approve / Reject / Edit / Regenerate.

### T-S06-033. RAGCardReviewDrawer (8 вкладок)

Target:
- `frontend/src/components/Wizard/review/RAGCardReviewDrawer.tsx`

Acceptance:
- Tabs: Overview, Metadata, Body, Source Trace, Validation, Versions, Review Log, Diff.
- Метаdata viewer + editor (toggle).
- Markdown viewer (sanitized) + editor (toggle).
- Source trace panel (links).
- Validation errors/warnings.
- Version history list.
- Review log timeline.
- Diff view between versions.

### T-S06-034. Review decision dialogs

Target:
- `frontend/src/components/Wizard/review/ReviewDecisionDialog.tsx`
- `frontend/src/components/Wizard/review/RejectReasonDialog.tsx`
- `frontend/src/components/Wizard/review/RegenerateReasonDialog.tsx`

Acceptance:
- Approve: optional comment.
- Reject: required dropdown + optional comment.
- Regenerate: required reason + optional instruction.

### T-S06-035. Bulk review toolbar

Target:
- `frontend/src/components/Wizard/review/BulkReviewToolbar.tsx`

Acceptance:
- Multi-select via checkboxes in table.
- Toolbar: «Approve выбранные (N)» / «Отклонить (N) с reason».
- Скрыт за feature flag `enable_bulk_approve`.

### T-S06-036. Frontend tests

Target:
- `frontend/src/components/Wizard/review/__tests__/*.test.tsx`

Acceptance:
- ReviewTable filters работают.
- Drawer переключается между tabs.
- Approve flow → table updates.
- Reject требует reason.
- Edit creates new version, shows diff.
- 12 frontend-тестов.

**Gate S5:** ~12 frontend-тестов зелёные + typecheck clean + build clean. Промежуточный commit.

---

## S6. Audit + observability (T-S06-037..039)

### T-S06-037. Audit actions

Target:
- `src/fe_bot/audit/service.py` (extend)

Acceptance:
- Использовать существующие `AuditAction.CARD_REVIEW_APPROVED/REJECTED/EDITED/REGENERATED` для основных действий.
- Новые actions: `CARD_REVIEW_EDIT_LOCK_ACQUIRED`, `CARD_REVIEW_EDIT_LOCK_RELEASED`, `CARD_REVIEW_BULK_APPROVED`.
- Wired в RAGCardReviewService + router.

### T-S06-038. Metrics integration

Target:
- `src/fe_bot/setup/card_review/metrics.py` (уже сделан в S2)
- Wired в DI.

Acceptance:
- Все 7 counters + 1 histogram (из T-S06-018) доступны через `/metrics`.
- Integration test: `tests/integration/test_review_audit_metrics.py` (10 тестов).

### T-S06-039. Structured logging

Target:
- `src/fe_bot/setup/card_review/service.py` (logger calls)

Acceptance:
- Log events: `rag_card_review_decision_made`, `rag_card_edited`, `rag_card_regenerate_requested`, `rag_card_bulk_review_completed`.
- Fields: setup_job_id, doc_id, card_version, reviewer_id, decision, reason, status_before, status_after, duration_ms, outcome.
- 4 integration-тестов.

**Gate S6:** ~14 integration-тестов зелёные.

---

## S7. Traceability + runbook (T-S06-040)

### T-S06-040. Docs + final commit

Target:
- `docs/traceability/setup-06.md` (новый)
- `docs/traceability/coverage-matrix.md` (extend)
- `docs/11-operations/rag-card-review-runbook.md` (новый)
- `docs/06-rag/card-lifecycle.md` (final update)

Acceptance:
- Traceability: 46 AC → tests mapping; permissions; audit/metrics реестр; known limits MVP.
- Coverage matrix: SETUP-06 covered (backend+UI).
- Runbook: запуск через UI/API, диагностика 5 типичных ошибок, восстановление state, наблюдаемость.
- Card lifecycle: финальная диаграмма SETUP-05→SETUP-06→SETUP-07.

**Gate S7:** все ~1400 тестов зелёные, mypy clean, ruff clean, frontend build clean. Финальный commit `SETUP-06: RAG card review (backend + frontend + docs)`.

---

## Связанные документы

- [SETUP-06 feature spec](../02-system/features/SETUP-06-rag-card-review.md)
- [SETUP-05 implementation plan](SETUP-05.tasks.md) — структурный аналог
- [Card lifecycle](../06-rag/card-lifecycle.md)
- [DTO catalog](../03-architecture/services/data-transfer-objects.md)
