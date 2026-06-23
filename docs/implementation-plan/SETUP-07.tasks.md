# SETUP-07 — Implementation plan

Реализация SETUP-07 «Валидация metadata и онтологии RAG-карточек» по слайсам S0..S7. Источник требований: [docs/02-system/features/SETUP-07-metadata-validation.md](../02-system/features/SETUP-07-metadata-validation.md).

## Контекст

- **Существующий каркас:** validators/rag_metadata_validator.py (305 строк, готов) + src/fe_bot/setup/metadata_validation/service.py (173 строки, базовый).
- **Зависимости:** SETUP-06 approved/ready_for_metadata_validation карточки; SETUP-08 потребитель METADATA_VALIDATED.

## Метрики плана

- **~25 задач** в 8 слайсах + Phase A.
- **~180 новых тестов**.
- **2 промежуточных commit** (после S3 backend и после S5 frontend).

---

## Phase A. Design

- A1. Feature spec — done (SETUP-07-metadata-validation.md).
- A2. Implementation plan — этот документ.

---

## S0. Schemas (T-S07-001..003)

### T-S07-001. ValidationRunDTO

`schemas/setup/validation_run.py` — агрегат прогона: validation_run_id, setup_job_id, status, started_at, finished_at, total/passed/warnings/failed/review_required, triggered_by.

### T-S07-002. ValidationSummaryDTO

`schemas/setup/validation_summary.py` — счётчики для UI: total, passed, warnings, failed, review_required, by_code (dict).

### T-S07-003. Расширение CardStatus

Уже есть METADATA_VALIDATED, READY_FOR_METADATA_VALIDATION. Проверить transitions для READY_FOR_METADATA_VALIDATION → METADATA_VALIDATED.

**Gate S0:** ~20 unit-тестов.

---

## S1. Repository (T-S07-004..005)

### T-S07-004. InMemoryValidationReportRepository

`src/fe_bot/setup/metadata_validation/report_repository.py` — Protocol + impl: `save(report, setup_job_id)`, `get(report_id)`, `latest_for_card(doc_id)`, `list_for_setup_job(setup_job_id, *, status_filter, code_filter)`, `count_by_status(setup_job_id)`. Snapshot persistence.

### T-S07-005. InMemoryValidationRunRepository

`.../run_repository.py` — `save_run`, `get_run`, `list_for_setup_job`.

**Gate S1:** ~18 unit-тестов.

---

## S2. Validator extensions (T-S07-006..007)

### T-S07-006. ValidatorRepairHints

Расширить validator: для каждого error_code добавить `repair_hint` (machine-readable suggestion).

### T-S07-007. ValidationCheckCategory

Группировка checks по категориям: REQUIRED_FIELDS, ONTOLOGY, REFERENCES, UNIQUENESS. Используется в фильтрах.

**Gate S2:** ~15 unit-тестов.

---

## S3. Service rewrite + events + SETUP-06 integration (T-S07-008..011)

### T-S07-008. Events

`src/fe_bot/setup/metadata_validation/events.py` — 3 events: ValidationRunStartedEvent, ValidationReportCreatedEvent, ValidationRunCompletedEvent.

### T-S07-009. MetadataValidationService rewrite

`src/fe_bot/setup/metadata_validation/service.py` — добавить:
- `report_repo` + `run_repo` + `event_bus` + `audit_service` + `metrics` + `card_registry`.
- `validate_for_job` создаёт ValidationRun + сохраняет каждый report.
- `validate_one(doc_id)` — single-card.
- `get_summary(setup_job_id)`.
- Audit `validation.run_triggered`, `validation.report_created`.
- Metrics: `validation_runs_total`, `validation_reports_total{status}`, `validation_duration_ms`.
- Structured log per run + per report.

### T-S07-010. Auto-validate hook в SETUP-06

После approve в SETUP-06 → trigger validate_one(doc_id) автоматически. Если passed → status: METADATA_VALIDATED.

### T-S07-011. DI wiring

dependencies.py — `_validation_report_repo`, `_validation_run_repo`, re-instantiate `_metadata_validation` с полным wiring. Snapshot persistence для 2 новых repo.

**Gate S3:** ~50 component+integration тестов. Промежуточный commit.

---

## S4. API + RBAC (T-S07-012..016)

### T-S07-012. Permissions

3 новых permissions: `KB_RAG_CARD_VALIDATION_READ`, `KB_RAG_CARD_VALIDATION_RUN`, `KB_RAG_CARD_VALIDATION_REFRESH`. Role matrix update.

### T-S07-013. API DTO

`src/fe_bot/api/setup/validation_dto.py` — request/response DTOs.

### T-S07-014. Router

`src/fe_bot/api/setup/validation_router.py` — 5 endpoints.

### T-S07-015. App wiring

include_router в app.py.

### T-S07-016. Integration tests

20 integration tests endpoints + RBAC + cross-job isolation.

**Gate S4:** ~20 integration тестов.

---

## S5. Frontend (T-S07-017..020)

### T-S07-017. API client + types

`frontend/src/api/validation.ts` + types.

### T-S07-018. ValidationSummaryCard

`frontend/src/components/Wizard/validation/ValidationSummaryCard.tsx`.

### T-S07-019. ValidationReportDrawer

`frontend/src/components/Wizard/validation/ValidationReportDrawer.tsx`.

### T-S07-020. ValidationStep + tests

Wizard step + 4 frontend tests.

**Gate S5:** ~4 frontend tests + typecheck clean + промежуточный commit.

---

## S6. Audit + metrics + structured logs (T-S07-021..022)

### T-S07-021. AuditAction VALIDATION_*

Audit actions: VALIDATION_RUN_TRIGGERED, VALIDATION_REPORT_CREATED, VALIDATION_ISSUE_RESOLVED.

### T-S07-022. Integration tests audit/metrics/logs

8 integration tests.

**Gate S6:** ~8 integration тестов.

---

## S7. Docs + final commit (T-S07-023)

### T-S07-023. Traceability + runbook

- docs/traceability/setup-07.md (новый).
- docs/traceability/coverage-matrix.md update.
- docs/11-operations/metadata-validation-runbook.md (новый).

**Gate S7:** все тесты зелёные, финальный commit `SETUP-07: metadata validation`.
