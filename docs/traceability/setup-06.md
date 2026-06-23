# SETUP-06 Traceability — RAG Card Review

Документ фиксирует реализованные слайсы SETUP-06 (Просмотр, редактирование и
подтверждение RAG-карточек) и прослеживает связи AC → task → код → тест.

## Слайсы

| Слайс | Содержимое | Статус |
| --- | --- | --- |
| Phase A | Feature spec (23 секции, 46 AC) + implementation plan | done |
| S0 | 6 schemas + 60 unit-тестов | done |
| S1 | 4 repositories + 37 unit-тестов | done |
| S2 | Validators + editor + versioning + readiness + metrics (55 unit) | done |
| S3 | RAGCardReviewService rewrite + 8 events + SETUP-05 integration (33 unit+component) | done |
| S4 | 9 API endpoints + 10 permissions + RBAC (22 integration) | done |
| S5 | Frontend (review table + drawer + 4 frontend tests) | done |
| S6 | Audit + metrics + structured logging (8 integration) | done |
| S7 | Traceability + runbook + final commit | done |

## Контракты

| DTO | Файл |
| --- | --- |
| `ReviewDecisionDTO` + `ReviewDecision` enum + `RejectReason` + `RegenerateReason` | [schemas/setup/review_decision.py](../../schemas/setup/review_decision.py) |
| `ReviewLogDTO` + `ReviewLogEventType` | [schemas/setup/review_log.py](../../schemas/setup/review_log.py) |
| `RAGCardVersionDTO` + `bump_version` | [schemas/setup/rag_card_version.py](../../schemas/setup/rag_card_version.py) |
| `RAGCardDiffDTO` + `MetadataFieldDiff` + `BodyDiff` | [schemas/setup/rag_card_diff.py](../../schemas/setup/rag_card_diff.py) |
| `RAGCardEditLockDTO` + `EditLockStatus` | [schemas/setup/rag_card_edit_lock.py](../../schemas/setup/rag_card_edit_lock.py) |
| `CardStatus` extension (4 новых статуса + transitions) | [schemas/rag/rag_card.py](../../schemas/rag/rag_card.py) |

## Реализация

| Компонент | Файл |
| --- | --- |
| 4 in-memory репозитория | [src/fe_bot/setup/card_review/decision_repository.py](../../src/fe_bot/setup/card_review/decision_repository.py), [.../log_repository.py](../../src/fe_bot/setup/card_review/log_repository.py), [.../version_repository.py](../../src/fe_bot/setup/card_review/version_repository.py), [.../edit_lock_repository.py](../../src/fe_bot/setup/card_review/edit_lock_repository.py) |
| Validators | [src/fe_bot/setup/card_review/validators/body.py](../../src/fe_bot/setup/card_review/validators/body.py), [.../source_trace.py](../../src/fe_bot/setup/card_review/validators/source_trace.py), [.../pre_approve.py](../../src/fe_bot/setup/card_review/validators/pre_approve.py) |
| Editor + Versioning + Readiness + Metrics | [src/fe_bot/setup/card_review/editor.py](../../src/fe_bot/setup/card_review/editor.py), [.../versioning.py](../../src/fe_bot/setup/card_review/versioning.py), [.../readiness.py](../../src/fe_bot/setup/card_review/readiness.py), [.../metrics.py](../../src/fe_bot/setup/card_review/metrics.py) |
| Service + Events | [src/fe_bot/setup/card_review/service.py](../../src/fe_bot/setup/card_review/service.py), [.../events.py](../../src/fe_bot/setup/card_review/events.py) |
| Permissions | [src/fe_bot/auth/permissions.py](../../src/fe_bot/auth/permissions.py) |
| API DTO + router | [src/fe_bot/api/setup/review_dto.py](../../src/fe_bot/api/setup/review_dto.py), [.../review_router.py](../../src/fe_bot/api/setup/review_router.py) |
| DI wiring + persistence | [src/fe_bot/api/dependencies.py](../../src/fe_bot/api/dependencies.py), [src/fe_bot/persistence/snapshot.py](../../src/fe_bot/persistence/snapshot.py), [src/fe_bot/app.py](../../src/fe_bot/app.py) |
| Frontend | [frontend/src/api/review.ts](../../frontend/src/api/review.ts), [.../api/types.ts](../../frontend/src/api/types.ts), [frontend/src/components/Wizard/review/RAGCardReviewTable.tsx](../../frontend/src/components/Wizard/review/RAGCardReviewTable.tsx), [.../RAGCardReviewDrawer.tsx](../../frontend/src/components/Wizard/review/RAGCardReviewDrawer.tsx), [frontend/src/components/Wizard/steps/ReviewCardsStep.tsx](../../frontend/src/components/Wizard/steps/ReviewCardsStep.tsx) |

## Тесты

| Уровень | Файл | Покрытие |
| --- | --- | --- |
| unit | [tests/unit/test_review_decision_schema.py](../../tests/unit/test_review_decision_schema.py) | 15 — DTO, enum, model_validator |
| unit | [tests/unit/test_review_log_schema.py](../../tests/unit/test_review_log_schema.py) | 10 |
| unit | [tests/unit/test_rag_card_version_schema.py](../../tests/unit/test_rag_card_version_schema.py) | 10 + bump_version |
| unit | [tests/unit/test_rag_card_diff_schema.py](../../tests/unit/test_rag_card_diff_schema.py) | 6 |
| unit | [tests/unit/test_rag_card_edit_lock_schema.py](../../tests/unit/test_rag_card_edit_lock_schema.py) | 6 |
| unit | [tests/unit/test_rag_card_status_setup06.py](../../tests/unit/test_rag_card_status_setup06.py) | 13 — все переходы |
| unit | [tests/unit/test_review_decision_repository.py](../../tests/unit/test_review_decision_repository.py) | 9 |
| unit | [tests/unit/test_review_log_repository.py](../../tests/unit/test_review_log_repository.py) | 7 |
| unit | [tests/unit/test_rag_card_version_repository.py](../../tests/unit/test_rag_card_version_repository.py) | 11 |
| unit | [tests/unit/test_edit_lock_repository.py](../../tests/unit/test_edit_lock_repository.py) | 10 |
| unit | [tests/unit/test_card_body_validator.py](../../tests/unit/test_card_body_validator.py) | 8 |
| unit | [tests/unit/test_source_trace_validator.py](../../tests/unit/test_source_trace_validator.py) | 7 |
| unit | [tests/unit/test_pre_approve_validation.py](../../tests/unit/test_pre_approve_validation.py) | 6 |
| unit | [tests/unit/test_card_editor_service.py](../../tests/unit/test_card_editor_service.py) | 11 |
| unit | [tests/unit/test_versioning_service.py](../../tests/unit/test_versioning_service.py) | 8 |
| unit | [tests/unit/test_review_readiness.py](../../tests/unit/test_review_readiness.py) | 8 |
| unit | [tests/unit/test_review_metrics_collector.py](../../tests/unit/test_review_metrics_collector.py) | 7 |
| unit | [tests/unit/test_review_events.py](../../tests/unit/test_review_events.py) | 10 |
| component | [tests/component/test_rag_card_review_service.py](../../tests/component/test_rag_card_review_service.py) | 23 — approve / reject / edit / regenerate / bulk / list / details |
| integration | [tests/integration/test_review_endpoints.py](../../tests/integration/test_review_endpoints.py) | 22 — 9 endpoints + RBAC + cross-job isolation |
| integration | [tests/integration/test_review_audit_metrics.py](../../tests/integration/test_review_audit_metrics.py) | 8 — audit + metrics + logs |
| frontend | [frontend/src/components/Wizard/review/__tests__/RAGCardReviewTable.test.tsx](../../frontend/src/components/Wizard/review/__tests__/RAGCardReviewTable.test.tsx) | 4 |

## Permissions

10 новых permissions из семейства `KB_RAG_CARD_*`:

| Permission | Roles | Endpoint(s) |
| --- | --- | --- |
| `kb.rag_card.list` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR, ADMIN | GET /rag-cards-review |
| `kb.rag_card.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR, ADMIN | GET /rag-cards-review/{doc_id} |
| `kb.rag_card.approve` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /review (approve) |
| `kb.rag_card.reject` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /review (reject) |
| `kb.rag_card.edit` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | PATCH /rag-cards-review/{doc_id} |
| `kb.rag_card.regenerate` | DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /regenerate |
| `kb.rag_card.version.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR, ADMIN | GET /versions |
| `kb.rag_card.diff.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR, ADMIN | GET /diff |
| `kb.rag_card.review_log.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR, ADMIN | GET /review-log |
| `kb.rag_card.bulk_review` | RAG_ADMIN, ADMIN | POST /bulk-review |

## Audit actions

| Action | Когда |
| --- | --- |
| `card.review_approved` | approve_card |
| `card.review_rejected` | reject_card |
| `card.review_edited` | edit_card |
| `rag_card.regenerate_triggered` | request_regeneration (используется существующий из SETUP-05) |

## Метрики

| Имя | Тип | Labels |
| --- | --- | --- |
| `rag_card_reviews_total` | counter | decision |
| `rag_card_approved_total` | counter | doc_type |
| `rag_card_rejected_total` | counter | doc_type, reason |
| `rag_card_edited_total` | counter | doc_type |
| `rag_card_regenerate_requested_total` | counter | doc_type |
| `rag_card_validation_blocked_approve_total` | counter | error_code |
| `rag_card_version_conflicts_total` | counter | — |
| `rag_card_review_duration_ms` | histogram | decision, doc_type |

## Structured logs

- `rag_card_review_decision_made` — approve/reject: setup_job_id, doc_id, card_version, reviewer_id, decision, status_before/after, duration_ms, outcome.
- `rag_card_edited` — edit: previous_card_version, new_card_version, metadata_changed, body_changed, change_reason.
- `rag_card_regenerate_requested` — regenerate: regenerate_request_id, generation_job_id, reason.
- `rag_card_bulk_review_completed` — bulk: bulk_review_id, total, approved, errors.

## AC → тест (46 AC)

Каждый AC из feature §19 покрыт минимум одним тестом из таблицы выше. Полный
mapping AC↔test см. в [docs/10-testing/SETUP-06-test-plan.md](../10-testing/SETUP-06-test-plan.md) (плановый артефакт; в этой
итерации использовалась inline-документация в самих тестах через имена методов).

## Known limits MVP

- В MVP — синхронный одиночный reviewer (multi-step approval отложено).
- Edit lock — in-memory; production требует Redis с TTL.
- Diff — структурное сравнение metadata + body_hash; full unified body diff
  реализован в `CardEditorService.calculate_diff` но не выставлен через API.
- `kb.rag_card.validation.read` и `kb.rag_card.source_trace.read` permissions
  определены в матрице ролей, но не закрывают отдельный endpoint в MVP
  (валидация и source trace входят в GET details).
- Legacy `/rag-cards/{doc_id}/review` endpoint сохранён для backward-compat;
  планируется deprecation после полного перехода UI на новый flow.
- Frontend — base components готовы; bulk approve UI и full diff view
  отложены до следующей итерации.

## Связанные документы

- [SETUP-05 traceability](setup-05.md) — структурный предшественник
- [SETUP-06 feature spec](../02-system/features/SETUP-06-rag-card-review.md)
- [SETUP-06 implementation plan](../implementation-plan/SETUP-06.tasks.md)
- [Card lifecycle](../06-rag/card-lifecycle.md)
- [Runbook](../11-operations/rag-card-review-runbook.md)
