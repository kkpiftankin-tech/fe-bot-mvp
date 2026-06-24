# SETUP-07 Traceability — Metadata Validation

Документ фиксирует реализованные слайсы SETUP-07 (Валидация metadata и
онтологии) и прослеживает связи AC → task → код → тест.

## Слайсы

| Слайс | Содержимое | Статус |
| --- | --- | --- |
| Phase A | Feature spec (16 секций, 21 AC) + implementation plan | done |
| S0 | 3 schemas (ValidationRun, ValidationSummary, ValidationReport extension) + 26 unit | done |
| S1 | 2 repositories (Report, Run) + 16 unit | done |
| S2 | Events + metrics + service rewrite + audit + DI + 9 component | done |
| S3 | 3 permissions + 5 API endpoints + 14 integration | done |
| S4 | SETUP-06 integration (auto-validate on approve) + 2 integration | done |
| S5 | Frontend (SummaryCard + ReportTable + 3 frontend) | done |
| S6 | Audit + metrics + structured logs integration tests (6 integration) | done |
| S7 | Traceability + runbook + final commit | done |

## Контракты

| DTO | Файл |
| --- | --- |
| `ValidationRunDTO` + `ValidationRunStatus` | [schemas/setup/validation_run.py](../../schemas/setup/validation_run.py) |
| `ValidationSummaryDTO` | [schemas/setup/validation_summary.py](../../schemas/setup/validation_summary.py) |
| `ValidationReport` + setup_job_id/card_version/policy_used/validation_run_id | [schemas/setup/validation_report.py](../../schemas/setup/validation_report.py) |

## Реализация

| Компонент | Файл |
| --- | --- |
| Repositories | [src/fe_bot/setup/metadata_validation/report_repository.py](../../src/fe_bot/setup/metadata_validation/report_repository.py), [.../run_repository.py](../../src/fe_bot/setup/metadata_validation/run_repository.py) |
| Events | [src/fe_bot/setup/metadata_validation/events.py](../../src/fe_bot/setup/metadata_validation/events.py) |
| Metrics | [src/fe_bot/setup/metadata_validation/metrics.py](../../src/fe_bot/setup/metadata_validation/metrics.py) |
| Service rewrite | [src/fe_bot/setup/metadata_validation/service.py](../../src/fe_bot/setup/metadata_validation/service.py) |
| Validator engine | [validators/rag_metadata_validator.py](../../validators/rag_metadata_validator.py) (без изменений в SETUP-07) |
| Audit actions | [src/fe_bot/audit/service.py](../../src/fe_bot/audit/service.py) (+3 VALIDATION_*) |
| Permissions | [src/fe_bot/auth/permissions.py](../../src/fe_bot/auth/permissions.py) (+3 KB_VALIDATION_*) |
| API | [src/fe_bot/api/setup/validation_dto.py](../../src/fe_bot/api/setup/validation_dto.py), [.../validation_router.py](../../src/fe_bot/api/setup/validation_router.py) |
| DI + app wiring | [src/fe_bot/api/dependencies.py](../../src/fe_bot/api/dependencies.py), [src/fe_bot/app.py](../../src/fe_bot/app.py), [src/fe_bot/persistence/snapshot.py](../../src/fe_bot/persistence/snapshot.py) |
| SETUP-06 hook | [src/fe_bot/setup/card_review/service.py](../../src/fe_bot/setup/card_review/service.py) — `approve_card` вызывает `validate_one` |
| Frontend | [frontend/src/api/validation.ts](../../frontend/src/api/validation.ts), [frontend/src/components/Wizard/validation/ValidationSummaryCard.tsx](../../frontend/src/components/Wizard/validation/ValidationSummaryCard.tsx), [.../ValidationReportTable.tsx](../../frontend/src/components/Wizard/validation/ValidationReportTable.tsx) |

## Тесты

| Уровень | Файл | Покрытие |
| --- | --- | --- |
| unit | [tests/unit/test_validation_run_schema.py](../../tests/unit/test_validation_run_schema.py) | 7 |
| unit | [tests/unit/test_validation_summary_schema.py](../../tests/unit/test_validation_summary_schema.py) | 4 |
| unit | [tests/unit/test_validation_report_schema_setup07.py](../../tests/unit/test_validation_report_schema_setup07.py) | 5 |
| unit | [tests/unit/test_validation_report_repository.py](../../tests/unit/test_validation_report_repository.py) | 8 |
| unit | [tests/unit/test_validation_run_repository.py](../../tests/unit/test_validation_run_repository.py) | 8 |
| component | [tests/component/test_metadata_validation_service_v2.py](../../tests/component/test_metadata_validation_service_v2.py) | 9 |
| integration | [tests/integration/test_validation_endpoints.py](../../tests/integration/test_validation_endpoints.py) | 14 — 5 endpoints + RBAC + cross-job |
| integration | [tests/integration/test_review_validation_integration.py](../../tests/integration/test_review_validation_integration.py) | 2 — SETUP-06 → SETUP-07 auto-validate |
| integration | [tests/integration/test_validation_audit_metrics.py](../../tests/integration/test_validation_audit_metrics.py) | 6 |
| frontend | [frontend/src/components/Wizard/validation/__tests__/ValidationSummaryCard.test.tsx](../../frontend/src/components/Wizard/validation/__tests__/ValidationSummaryCard.test.tsx) | 3 |

## Permissions

3 новых из семейства `KB_VALIDATION_*`:

| Permission | Roles | Endpoint(s) |
| --- | --- | --- |
| `kb.validation.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN, AUDITOR | GET /reports, GET /summary, GET /reports/{doc_id} |
| `kb.validation.run` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /run |
| `kb.validation.refresh` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /reports/{doc_id}/refresh |

## Audit actions

| Action | Когда |
| --- | --- |
| `validation.run_triggered` | POST /validation/run |
| `validation.report_created` | per report (включая refresh) |
| `validation.issue_resolved` | (reserved для будущего auto-resolve flow) |

## Метрики

| Имя | Тип | Labels |
| --- | --- | --- |
| `validation_runs_total` | counter | outcome |
| `validation_reports_total` | counter | status |
| `validation_issues_total` | counter | code, severity |
| `validation_status_transitions_total` | counter | target |
| `validation_card_duration_ms` | histogram | — |
| `validation_run_duration_ms` | histogram | — |

## Structured logs

- `validation_run_completed` — setup_job_id, validation_run_id, policy,
  total/passed/warnings/failed/review_required, duration_ms, outcome.

## AC → тест

21 AC покрыты тестами; inline-документация в названиях методов тестов.

## Known limits MVP

- ValidationRun не поддерживает cancel/retry — однопроходный sync flow.
- ValidationReport persisted в in-memory (Redis/Postgres — план).
- API не поддерживает batch refresh — только per-card.
- T-S07-017 (auto-validate on approve): если carda APPROVED + validation
  FAILED, статус карточки автоматически переходит в REVIEW_REQUIRED через
  внутренний `_apply_validation` (см. service.py).
- Frontend wizard step ещё не подключён (component компоненты готовы, но
  ValidationStep в WizardLayout — отдельная задача).

## Связанные документы

- [SETUP-06 traceability](setup-06.md)
- [SETUP-07 feature spec](../02-system/features/SETUP-07-metadata-validation.md)
- [SETUP-07 implementation plan](../implementation-plan/SETUP-07.tasks.md)
- [Metadata schema](../06-rag/metadata-schema.md)
