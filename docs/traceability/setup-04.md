# SETUP-04 Traceability — Document Parsing

Документ фиксирует реализованные слайсы SETUP-04 (Document Parsing) и
прослеживает связи AC → task → код → тест.

## Слайсы

| Слайс | Содержимое | Статус |
| --- | --- | --- |
| S0 | DTO (ParseJob, ParseJobDocument, ParsedSection, SectionClassification, DocumentParseReport) | done |
| S1 | 4 in-memory repository (ParseJob, ParseJobDocument, ParsedSection, DocumentParseReport) | done |
| S2 | ParserRegistry + 7 ParserStrategy (Markdown, Text, CSV, JSON, PDF, DOCX, XLSX) | done |
| S3 | SectionBoundaryDetector, rule-based SectionClassifier | done |
| S4 | DocumentParserOrchestrator + SourceLifecycle/processing log/lineage integration + 10 parse-events | done |
| S5 | 5 KB_PARSE_* permissions + 6 endpoints (/parse-jobs, status, report, sections, cancel, retry) | done |
| S6 | Frontend (Wizard parsing step) | deferred (frontend stack) |
| S7 | Docs & traceability update | done |

## Контракты

| DTO | Файл |
| --- | --- |
| ParseJob, ParseJobStatus, ParseErrorCode, ParserStrategy | [schemas/setup/parse_job.py](../../schemas/setup/parse_job.py) |
| ParseJobDocument, ParseJobDocumentStatus | [schemas/setup/parse_job_document.py](../../schemas/setup/parse_job_document.py) |
| ParsedSection, SectionType, ParsedSectionStatus | [schemas/setup/parsed_section.py](../../schemas/setup/parsed_section.py) |
| SectionClassification, ClassificationMethod | [schemas/setup/section_classification.py](../../schemas/setup/section_classification.py) |
| DocumentParseReport, ParseError, SectionsSummary | [schemas/setup/parse_report.py](../../schemas/setup/parse_report.py) |

## Реализация

| Компонент | Файл |
| --- | --- |
| 4 in-memory репозитория | [src/fe_bot/setup/parser/job_repository.py](../../src/fe_bot/setup/parser/job_repository.py), [.../document_repository.py](../../src/fe_bot/setup/parser/document_repository.py), [.../section_repository.py](../../src/fe_bot/setup/parser/section_repository.py), [.../report_repository.py](../../src/fe_bot/setup/parser/report_repository.py) |
| Реестр + стратегии | [src/fe_bot/setup/parser/registry.py](../../src/fe_bot/setup/parser/registry.py), [.../strategies/](../../src/fe_bot/setup/parser/strategies/) |
| Boundary detector + classifier | [src/fe_bot/setup/parser/boundary.py](../../src/fe_bot/setup/parser/boundary.py), [.../classifier.py](../../src/fe_bot/setup/parser/classifier.py) |
| Orchestrator + lifecycle integration | [src/fe_bot/setup/parser/orchestrator.py](../../src/fe_bot/setup/parser/orchestrator.py) |
| Events | [src/fe_bot/setup/parser/events.py](../../src/fe_bot/setup/parser/events.py) |
| Permissions | [src/fe_bot/auth/permissions.py](../../src/fe_bot/auth/permissions.py) |
| API DTO + router | [src/fe_bot/api/setup/parse_dto.py](../../src/fe_bot/api/setup/parse_dto.py), [.../parse_router.py](../../src/fe_bot/api/setup/parse_router.py) |
| DI wiring | [src/fe_bot/api/dependencies.py](../../src/fe_bot/api/dependencies.py), [src/fe_bot/app.py](../../src/fe_bot/app.py) |

## Тесты

| Уровень | Файл | Покрытие |
| --- | --- | --- |
| unit | [tests/unit/test_parse_job_repository.py](../../tests/unit/test_parse_job_repository.py) | ParseJob CRUD + active-job uniqueness |
| unit | [tests/unit/test_parse_job_document_repository.py](../../tests/unit/test_parse_job_document_repository.py) | per-document status filtering |
| unit | [tests/unit/test_parsed_section_repository.py](../../tests/unit/test_parsed_section_repository.py) | 4-fold index, atomic batch save |
| unit | [tests/unit/test_parse_report_repository.py](../../tests/unit/test_parse_report_repository.py) | unique (job, doc), last-write-wins |
| unit | [tests/unit/test_parser_registry.py](../../tests/unit/test_parser_registry.py) | content-type resolution |
| unit | [tests/unit/test_parser_strategies.py](../../tests/unit/test_parser_strategies.py) | 24 кейса по всем 7 стратегиям |
| unit | [tests/unit/test_section_boundary_and_classifier.py](../../tests/unit/test_section_boundary_and_classifier.py) | overlap detection, keyword classification |
| component | [tests/component/test_document_parser_orchestrator.py](../../tests/component/test_document_parser_orchestrator.py) | happy/partial/full failure, events, lifecycle |
| integration | [tests/integration/test_parse_jobs_endpoints.py](../../tests/integration/test_parse_jobs_endpoints.py) | 6 endpoints, RBAC, error paths |

## Permissions

| Permission | Role(s) | Endpoint(s) |
| --- | --- | --- |
| `kb.parse.run` | USER, DOMAIN_EXPERT, RAG_ADMIN | POST /parse-jobs |
| `kb.parse.status.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR | GET /parse-jobs/{id}, /report |
| `kb.section.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR | GET /parse-jobs/{id}/sections |
| `kb.parse.retry` | DOMAIN_EXPERT, RAG_ADMIN | POST /documents/{src_id}/retry |
| `kb.parse.cancel` | RAG_ADMIN, ADMIN | POST /parse-jobs/{id}/cancel |

## Известные ограничения

- S6 Frontend (ParseJobProgressPanel, SectionTreeView, ParseReportDrawer, WizardParsingStep) перенесён в отдельный фронтенд-инкремент.
- ParseJob исполняется синхронно in-process; асинхронное исполнение и очереди появятся после внедрения worker-сервиса.
- OCR явно исключён из scope (см. SETUP-04 spec §4.2).
- Retry endpoint в MVP создаёт новый ParseJob для одного документа — нет переиспользования старого.
