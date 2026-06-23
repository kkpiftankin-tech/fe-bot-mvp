# Матрица покрытия

Roll-up матрица: какие docs, контракты, промпты, валидаторы и тесты покрывают каждую фичу.

## Схема

| Feature | Use Cases | Agents | Contracts | Prompts | Validators | Tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SETUP-01 | docs/02-system/features/SETUP-01-*.md | — | schemas/setup/*.py | — | validators/ | tests/unit/ tests/integration/ | covered |
| SETUP-02 | docs/02-system/features/SETUP-02-*.md | — | schemas/setup/upload_*.py | — | — | tests/unit/ tests/integration/ | covered |
| SETUP-03 | docs/02-system/features/SETUP-03-*.md | — | schemas/setup/status_history.py schemas/setup/lineage.py | — | — | tests/unit/ tests/integration/ | covered |
| SETUP-04 | docs/02-system/features/SETUP-04-*.md | — | schemas/setup/parse_job.py schemas/setup/parsed_section.py schemas/setup/parse_report.py schemas/setup/parse_job_document.py schemas/setup/section_classification.py | — | — | tests/unit/test_parse_job_repository.py tests/unit/test_parsed_section_repository.py tests/unit/test_parser_strategies.py tests/unit/test_section_boundary_and_classifier.py tests/component/test_document_parser_orchestrator.py tests/integration/test_parse_jobs_endpoints.py | covered (backend, no FE) |
| SETUP-05 | docs/02-system/features/SETUP-05-rag-cards-generation.md | — | schemas/setup/rag_card_generation_job.py schemas/setup/rag_card_generation_job_section.py schemas/setup/rag_card_metadata.py schemas/setup/rag_card_markdown.py schemas/setup/rag_card_source_link.py schemas/setup/rag_card_generation_report.py | prompts/rag_card/ | rag/ontology/ontology_v1.yaml + CardValidationPrecheck | tests/unit/test_rag_card_*.py tests/component/test_rag_card_generation_orchestrator.py tests/integration/test_rag_cards_endpoints.py tests/integration/test_rag_card_audit_metrics.py | covered (backend + UI) |
| SETUP-06 | docs/02-system/features/SETUP-06-rag-card-review.md | — | schemas/setup/review_decision.py schemas/setup/review_log.py schemas/setup/rag_card_version.py schemas/setup/rag_card_diff.py schemas/setup/rag_card_edit_lock.py | — | CardSourceTraceValidator + CardBodyValidator + PreApproveValidationOrchestrator | tests/unit/test_review_*.py tests/unit/test_card_*.py tests/unit/test_pre_approve_validation.py tests/unit/test_versioning_service.py tests/component/test_rag_card_review_service.py tests/integration/test_review_endpoints.py tests/integration/test_review_audit_metrics.py | covered (backend + UI) |

## Значения статусов

- `planned` — запись есть, но артефактов ещё нет.
- `in-progress` — часть артефактов на месте, есть пробелы.
- `covered` — каждый обязательный столбец заполнен и тесты проходят.
- `deprecated` — фича выведена; строка остаётся с датой для истории.

## TODO

- Заполняется по мере добавления фич в `docs/02-system/features/`.

## Связанные карты

- [feature-to-service-map.md](feature-to-service-map.md) — фича → SVC
- [dto-to-service-map.md](dto-to-service-map.md) — DTO → producer/consumer SVC
- [agent-to-contract-map.md](agent-to-contract-map.md) — агент → schema → tests
- [rag-coverage-matrix.md](rag-coverage-matrix.md) — фаза → retrieval policy → evaluation case
