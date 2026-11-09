# SETUP-05 Traceability — RAG Card Generation

Документ фиксирует реализованные слайсы SETUP-05 (Автоматическая генерация
RAG-карточек) и прослеживает связи AC → task → код → тест.

## Слайсы

| Слайс | Содержимое | Статус |
| --- | --- | --- |
| Phase A | 7 design-артефактов (feature doc, DTO, lifecycle, metadata, test plan, prompts, ontology v1) | done |
| S0 | 7 DTO + state machine + 69 unit-тестов | done |
| S1 | 5 in-memory repository (job, job_section, card_registry extension, source_link, report) + 46 unit | done |
| S2 | Detеrministic компоненты: OntologyMapper, PromptRegistry, DocTypeDetector, MetadataExtractor, DocIdGenerator (+66 unit) | done |
| S3 | LLMCardAdapter, CardValidationPrecheck, MarkdownBuilder, ConfidenceCalculator (+42 unit) | done |
| S4 | RAGCardGenerationOrchestrator + 8 events + lifecycle integration (+14 component) | done |
| S5 | 5 permissions + 9 API endpoints + 20 integration | done |
| S6 | Frontend (Wizard step «4. Генерация RAG-карточек», RAGCardList, PreviewDrawer, LowConfidencePanel) | done |
| S7 | Audit + metrics + structured logging + traceability + runbook (+9 integration) | done |

## Контракты (DTO-59..66)

| DTO | Файл |
| --- | --- |
| RAGCardGenerationJob + RAGCardGenerationJobStatus + RAGCardGenerationErrorCode | [schemas/setup/rag_card_generation_job.py](../../schemas/setup/rag_card_generation_job.py) |
| RAGCardGenerationJobSection + RAGCardGenerationJobSectionStatus + CardConfidenceLevel | [schemas/setup/rag_card_generation_job_section.py](../../schemas/setup/rag_card_generation_job_section.py) |
| RAGCardMetadataDTO + FeatureTableSpec + ValidationRuleSpec | [schemas/setup/rag_card_metadata.py](../../schemas/setup/rag_card_metadata.py) |
| RAGCardMarkdownDTO | [schemas/setup/rag_card_markdown.py](../../schemas/setup/rag_card_markdown.py) |
| RAGCardSourceLinkDTO | [schemas/setup/rag_card_source_link.py](../../schemas/setup/rag_card_source_link.py) |
| CardGenerationReportDTO + CardGenerationSummary | [schemas/setup/rag_card_generation_report.py](../../schemas/setup/rag_card_generation_report.py) |
| RAGCard расширение (6 новых статусов + 7 опц. полей) | [schemas/rag/rag_card.py](../../schemas/rag/rag_card.py) |

## Реализация

| Компонент | Файл |
| --- | --- |
| 5 in-memory репозиториев | [src/fe_bot/setup/rag_card_generation/job_repository.py](../../src/fe_bot/setup/rag_card_generation/job_repository.py), [.../job_section_repository.py](../../src/fe_bot/setup/rag_card_generation/job_section_repository.py), [.../source_link_repository.py](../../src/fe_bot/setup/rag_card_generation/source_link_repository.py), [.../report_repository.py](../../src/fe_bot/setup/rag_card_generation/report_repository.py) |
| Card registry extension | [src/fe_bot/setup/card_registry/service.py](../../src/fe_bot/setup/card_registry/service.py) |
| Deterministic компоненты | [src/fe_bot/setup/rag_card_generation/ontology_mapper.py](../../src/fe_bot/setup/rag_card_generation/ontology_mapper.py), [.../prompt_registry.py](../../src/fe_bot/setup/rag_card_generation/prompt_registry.py), [.../doc_type_detector.py](../../src/fe_bot/setup/rag_card_generation/doc_type_detector.py), [.../metadata_extractor.py](../../src/fe_bot/setup/rag_card_generation/metadata_extractor.py), [.../doc_id_generator.py](../../src/fe_bot/setup/rag_card_generation/doc_id_generator.py) |
| LLM / precheck / markdown / confidence | [src/fe_bot/setup/rag_card_generation/llm_adapter.py](../../src/fe_bot/setup/rag_card_generation/llm_adapter.py), [.../precheck.py](../../src/fe_bot/setup/rag_card_generation/precheck.py), [.../markdown_builder.py](../../src/fe_bot/setup/rag_card_generation/markdown_builder.py), [.../confidence_calculator.py](../../src/fe_bot/setup/rag_card_generation/confidence_calculator.py) |
| Orchestrator + events | [src/fe_bot/setup/rag_card_generation/orchestrator.py](../../src/fe_bot/setup/rag_card_generation/orchestrator.py), [.../events.py](../../src/fe_bot/setup/rag_card_generation/events.py) |
| Audit actions | [src/fe_bot/audit/service.py](../../src/fe_bot/audit/service.py) (5 новых RAG_CARD_*) |
| Permissions | [src/fe_bot/auth/permissions.py](../../src/fe_bot/auth/permissions.py) (5 новых KB_RAG_CARD_*) |
| API DTO + router | [src/fe_bot/api/setup/rag_cards_dto.py](../../src/fe_bot/api/setup/rag_cards_dto.py), [.../rag_cards_router.py](../../src/fe_bot/api/setup/rag_cards_router.py) |
| DI wiring + persistence snapshot | [src/fe_bot/api/dependencies.py](../../src/fe_bot/api/dependencies.py), [src/fe_bot/persistence/snapshot.py](../../src/fe_bot/persistence/snapshot.py), [src/fe_bot/app.py](../../src/fe_bot/app.py) |
| Prompts + ontology | [prompts/rag_card/](../../prompts/rag_card/), [rag/ontology/ontology_v1.yaml](../../rag/ontology/ontology_v1.yaml) |
| Frontend | [frontend/src/api/rag_cards.ts](../../frontend/src/api/rag_cards.ts), [frontend/src/components/Wizard/steps/RAGCardGenerationStep.tsx](../../frontend/src/components/Wizard/steps/RAGCardGenerationStep.tsx), [.../rag/RAGCardList.tsx](../../frontend/src/components/Wizard/rag/RAGCardList.tsx), [.../rag/RAGCardPreviewDrawer.tsx](../../frontend/src/components/Wizard/rag/RAGCardPreviewDrawer.tsx), [.../rag/LowConfidenceCardsPanel.tsx](../../frontend/src/components/Wizard/rag/LowConfidenceCardsPanel.tsx) |

## Тесты

| Уровень | Файл | Покрытие |
| --- | --- | --- |
| unit | [tests/unit/test_rag_card_generation_job.py](../../tests/unit/test_rag_card_generation_job.py) | state machine, 15 error codes, http_status_for |
| unit | [tests/unit/test_rag_card_generation_job_section.py](../../tests/unit/test_rag_card_generation_job_section.py) | section state, confidence buckets |
| unit | [tests/unit/test_rag_card_metadata_schemas.py](../../tests/unit/test_rag_card_metadata_schemas.py) | front matter DTO, feature tables, validation rules |
| unit | [tests/unit/test_rag_card_markdown.py](../../tests/unit/test_rag_card_markdown.py) | parse/from_parts roundtrip |
| unit | [tests/unit/test_rag_card_source_link.py](../../tests/unit/test_rag_card_source_link.py) | frozen lineage relation |
| unit | [tests/unit/test_rag_card_generation_report.py](../../tests/unit/test_rag_card_generation_report.py) | summary aggregation |
| unit | [tests/unit/test_rag_card_generation_repositories.py](../../tests/unit/test_rag_card_generation_repositories.py) | 5 repositories CRUD, idempotency |
| unit | [tests/unit/test_card_registry_setup05_extension.py](../../tests/unit/test_card_registry_setup05_extension.py) | save_version, list_for_setup_job, attach_artifact |
| unit | [tests/unit/test_ontology_mapper.py](../../tests/unit/test_ontology_mapper.py) | synonyms, case-insensitive lookup, OntologyWarning |
| unit | [tests/unit/test_prompt_registry.py](../../tests/unit/test_prompt_registry.py) | template loading + lenient render |
| unit | [tests/unit/test_doc_type_detector.py](../../tests/unit/test_doc_type_detector.py) | rule-based mapping + keyword fallback |
| unit | [tests/unit/test_metadata_extractor.py](../../tests/unit/test_metadata_extractor.py) | retrieval tags TF, columns, feature tables, validation hints |
| unit | [tests/unit/test_doc_id_generator.py](../../tests/unit/test_doc_id_generator.py) | translit, version bump, gap-filling |
| unit | [tests/unit/test_llm_card_adapter.py](../../tests/unit/test_llm_card_adapter.py) | 3 modes, FE_BOT_FORCE_FALLBACK, error mapping |
| unit | [tests/unit/test_card_validation_precheck.py](../../tests/unit/test_card_validation_precheck.py) | 6 blocking errors + 2 warnings |
| unit | [tests/unit/test_markdown_builder.py](../../tests/unit/test_markdown_builder.py) | sanitization, key order |
| unit | [tests/unit/test_confidence_calculator.py](../../tests/unit/test_confidence_calculator.py) | score → bucket boundaries |
| component | [tests/component/test_rag_card_generation_orchestrator.py](../../tests/component/test_rag_card_generation_orchestrator.py) | full pipeline, events, lifecycle |
| integration | [tests/integration/test_rag_cards_endpoints.py](../../tests/integration/test_rag_cards_endpoints.py) | 9 endpoints, RBAC, cross-job isolation |
| integration | [tests/integration/test_rag_card_audit_metrics.py](../../tests/integration/test_rag_card_audit_metrics.py) | 5 audit actions, counters, histograms, structured logs |

## Планируемое: единая классификация ([ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md))

Реализованные слайсы S0–S7 выше соответствуют прежнему дизайну (`DocTypeDetector` по `section_type`, онтологические поля от LLM). Целевой дизайн добавляет AC-52..60 и меняет AC-10, AC-17; ни реализации, ни тестов под них пока нет. Расхождение зафиксировано в [TD-HTC-004](../tech-debt/TD-HTC-004-duplicate-classification-in-card-generation.md).

| AC | Что проверяется | Целевой тест (планируется) | Статус |
| --- | --- | --- | --- |
| AC-10, AC-17 | `doc_type` из `doc_type_hint`; хинт вне поддерживаемых типов → `INVALID_DOC_TYPE` | `tests/unit/test_classification_metadata_resolver.py` | planned (сейчас покрыто `test_doc_type_detector.py` для прежней логики) |
| AC-52, AC-59 | Поля карточки равны `resolved_hints`; детерминизм | `tests/unit/test_classification_metadata_resolver.py` | planned |
| AC-53 | Промпт не просит `doc_type` и онтологические поля; ответ LLM их не меняет | `tests/prompt_eval/` + `tests/unit/test_llm_card_adapter.py` | planned |
| AC-54, AC-55 | Нет `doc_type_hint` / `classifier_result` → `DOC_TYPE_HINT_MISSING`, LLM не вызывается | `tests/component/test_rag_card_generation_orchestrator.py` | planned |
| AC-56 | Нет `domain_hint` / `phase_hint` → `metadata_incomplete` | `tests/component/test_rag_card_generation_orchestrator.py` | planned |
| AC-57 | Правка хинта + повтор генерации без перепарсинга | `tests/integration/` (SETUP-13 + SETUP-05) | planned |
| AC-58 | `classifier_path`, `classifier_tree_version` в front matter | `tests/unit/test_rag_card_metadata_schemas.py` | planned |
| AC-60 | Доля `DOC_TYPE_HINT_MISSING` в отчёте job | `tests/unit/test_rag_card_generation_report.py` | planned |

## Permissions

| Permission | Role(s) | Endpoint(s) |
| --- | --- | --- |
| `kb.rag_card.generate` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /rag-cards/generate, POST /rag-card-generation-jobs/{id}/run, POST /rag-card-generation-jobs/{id}/cancel |
| `kb.rag_card.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN, AUDITOR | GET /rag-card-generation-jobs/{id}, GET /report, GET /rag-cards-catalog, GET /rag-cards/{doc_id} |
| `kb.rag_card.preview` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | GET /rag-cards/{doc_id}/preview |
| `kb.rag_card.regenerate` | DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /rag-cards/{doc_id}/regenerate |
| `kb.rag_card.lineage.read` | DOMAIN_EXPERT, RAG_ADMIN, ADMIN, AUDITOR | (lineage запросы — встроены в preview/details) |

## Audit actions (T-S05-039)

| Action | Когда |
| --- | --- |
| `rag_card.generation_triggered` | create_job (POST /rag-cards/generate) |
| `rag_card.generated` | per card (после успешной генерации) |
| `rag_card.regenerate_triggered` | POST /rag-cards/{doc_id}/regenerate |
| `rag_card.review_required` | per card с low/medium confidence |
| `rag_card.generation_cancelled` | POST /rag-card-generation-jobs/{id}/cancel |

## Метрики

| Имя | Тип | Labels |
| --- | --- | --- |
| `rag_card_generation_jobs_total` | counter | outcome |
| `rag_cards_generated_total` | counter | doc_type, confidence_bucket |
| `rag_cards_failed_total` | counter | error_code |
| `rag_card_generation_duration_ms` | histogram | doc_type |

## Structured log events (T-S05-040)

- `rag_card_generation_job_started` — generation_job_id, setup_job_id, total_sections, requested_by
- `rag_card_generation_job_finished` — + generated_cards, failed_sections, review_required_cards, duration_ms, outcome
- `rag_card_generated` — per-card: generation_job_id, section_id, doc_id, doc_type, prompt_template_version, ontology_version, llm_model, confidence_level, duration_ms, outcome, used_fallback, attempts
- `rag_card_generation_failed` — per-section failure: generation_job_id, section_id, doc_type, error_code, outcome

## AC → тест (51 AC из спека)

Полный тест-план: [docs/10-testing/SETUP-05-test-plan.md](../10-testing/SETUP-05-test-plan.md).

Минимум 1 тест на AC; 51 AC покрыты комбинацией unit (S0..S3) + component (S4) + integration (S5, S7) + frontend smoke (S6).

## Known limits MVP

- Синхронный in-process run (асинхронная очередь — out of scope MVP).
- Нет relationship_card между карточками.
- Нет auto-repair: failed карточки требуют manual regenerate.
- Нет автоматического retry на section level (только на LLM-вызовах внутри adapter).
- Frontend: один setup_job_id в localStorage; для мульти-окна — будущая фича.

## Связанные документы

- [SETUP-04 traceability](setup-04.md) — структурный аналог
- [SETUP-05 implementation plan](../implementation-plan/SETUP-05.tasks.md)
- [SETUP-05 feature](../02-system/features/SETUP-05-rag-cards-generation.md)
- [SETUP-05 test plan](../10-testing/SETUP-05-test-plan.md)
- [RAG card lifecycle](../06-rag/card-lifecycle.md)
- [Runbook](../11-operations/rag-card-generation-runbook.md)
