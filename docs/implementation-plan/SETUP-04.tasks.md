# SETUP-04 — Document Parsing implementation plan

**Feature spec:** [docs/02-system/features/SETUP-04-document-parsing.md](../02-system/features/SETUP-04-document-parsing.md) + детальная спека (48 AC, §11.2 таблицы, §15 DTO, §16 API, §19 AC).

**Цель:** превратить исходные документы (MD, TXT, PDF, DOCX, XLSX, CSV, JSON) в типизированные адресуемые секции (`ParsedSection`), готовые к RAG-карточкам. Реализовать ParseJob-оркестрацию, репозитории, API и UI.

**Scope-решения (закреплены 2026-06-13):**

- Parsers: Markdown (адаптация `markdown_parser.py`) + TXT/CSV/JSON (адаптация `text_parsers.py`) + PDF (`pypdf`, text layer only, no OCR) + DOCX (`python-docx`) + XLSX (`openpyxl`, каждый sheet = section). OCR — out of scope (§4.2).
- Section Classifier: rule-based only (MVP); LLM-fallback — post-MVP stub за feature flag.
- ParseJob: отдельная lifecycle entity; retry создаёт новый ParseJob, а не переиспользует старый.
- Все репозитории — in-memory (Protocol + Lock), PostgreSQL — INF-002.
- Stubs `parse_pdf` / `parse_docx` / `parse_xlsx` из `text_parsers.py` удаляются и переносятся в отдельные стратегии.

**Total tasks:** 30 в 8 вертикальных слайсах.

---

## Зависимости между слайсами

```
S0 (schemas — уже сделано) →
S1 (repositories) →
S2 (parser strategies) →
S3 (boundary + classifier) →
S4 (orchestrator + SourceLifecycle integration) →
S5 (API endpoints) →
S6 (frontend) →
S7 (resilience + audit + docs)
```

Frontend (S6) может стартовать параллельно с S5 (когда S4 готов).
S2 и S3 могут идти параллельно после S1.

---

## Уже выполнено в S0 (текущая сессия 2026-06-13)

Следующие задачи **полностью закрыты** и помечены `✓`:

| ID | Файл | Статус |
|---|---|---|
| T-S04-001 | `schemas/setup/parsed_section.py` расширен | ✓ |
| T-S04-002 | `schemas/setup/parse_job.py` создан | ✓ |
| T-S04-003 | `schemas/setup/parse_job_document.py` создан | ✓ |
| T-S04-004 | `schemas/setup/section_classification.py` создан | ✓ |
| T-S04-005 | `schemas/setup/parse_report.py` создан | ✓ |

Доп. выполнено: `docs/03-architecture/services/data-transfer-objects.md` обновлён (DTO-54..58), регрессия исправлена (859/859 passed, mypy clean, ruff clean).

---

## Risks

- **PDF без text layer** (`PDF_TEXT_LAYER_NOT_FOUND`): `pypdf` возвращает пустой текст для scanned PDF. Обрабатываем как `ParseJobDocumentStatus.FAILED` с `retryable=False`, не как падение всего ParseJob. Митигирует T-S04-015.
- **XLSX с большим числом строк**: `openpyxl` читает в память. Лимит `max_rows_per_sheet` (default 500) с truncation warning. Митигирует T-S04-016.
- **Markdown parser backward-compat**: `parse_markdown` принимает `setup_job_id` (old) и `parse_job_id` (new) через AliasChoices. При рефакторинге на стратегии — не сломать существующие тесты `test_markdown_parser.py`. Блокирующий для T-S04-011.
- **`text_parsers.py` stubs удаляются**: `parse_pdf`, `parse_docx`, `parse_xlsx` переносятся. `DocumentParserService` (старый) также удаляется / заменяется `DocumentParserOrchestrator`. Регрессия покрывается T-S04-029.
- **Concurrent ParseJob**: PARSE_JOB_ALREADY_RUNNING должен проверяться атомарно. In-memory Lock в репозитории предотвращает гонки, но не persistent. Митигирует T-S04-018.

---

## Открытые вопросы (из §22.3 спека)

| Вопрос | Дефолт MVP | Блокирует |
|---|---|---|
| `confidence_threshold` для LOW_CONFIDENCE | 0.7 | T-S04-018 |
| `max_section_size_chars` | 8000 | T-S04-012 |
| `parse_timeout_sec` per document | 120 | T-S04-018 |
| Иерархический `parent_section_id` для Markdown H2→H1 | Реализовать | T-S04-011 |
| Retry создаёт новый ParseJob или переиспользует? | Новый ParseJob | T-S04-023 |
| `section.classification.low_confidence` event threshold | < 0.5 | T-S04-020 |

---

## S0. Schemas + DTOs (foundation) — ВЫПОЛНЕНО

### T-S04-001. ParsedSection расширение ✓ ВЫПОЛНЕНО

Target:
- `schemas/setup/parsed_section.py`
- `tests/unit/test_parsers.py` (проверить backward-compat)

Acceptance:
- Поля `section_index`, `parent_section_id`, `heading_path`, `section_status`, `content_hash`, `classification_method`, `structural_payload` присутствуют.
- `SectionType.VALIDATION_RULE`, `QUESTION_TEMPLATE`, `UNKNOWN` добавлены; `OTHER` сохранён как deprecated alias.
- `ParsedSectionStatus` enum с 7 значениями определён.
- `content_hash` автовычисляется SHA-256 если не передан.
- Backward-compat: `section_path` и `setup_job_id` принимаются через `AliasChoices`.
- 859/859 тестов проходят после изменений.

Зависит от: SETUP-03 ✓

---

### T-S04-002. ParseJob DTO + state machine ✓ ВЫПОЛНЕНО

Target:
- `schemas/setup/parse_job.py`

Acceptance:
- `ParseJobStatus` (7 значений), `ParseErrorCode` (13 кодов), `ParserStrategy` (7 стратегий) определены.
- `PARSE_JOB_ALLOWED_TRANSITIONS` — граф с terminal-статусами.
- `ParseJob.transition_to()` бросает `InvalidParseJobTransitionError` при недопустимых переходах.
- `http_status_for(ParseErrorCode)` маппинг (400/404/409/422/500/504).
- `counters_consistent` validator: processed + failed <= total.

Зависит от: T-S04-001

---

### T-S04-003. ParseJobDocument DTO ✓ ВЫПОЛНЕНО

Target:
- `schemas/setup/parse_job_document.py`

Acceptance:
- `ParseJobDocumentStatus` (5 значений) определён.
- `ParseJobDocument` с `parser_strategy`, счётчиками секций, тайминг полями.
- `_low_confidence_not_exceed_total` validator работает.
- `_finished_after_started` validator работает.

Зависит от: T-S04-002

---

### T-S04-004. SectionClassification DTO ✓ ВЫПОЛНЕНО

Target:
- `schemas/setup/section_classification.py`

Acceptance:
- `ClassificationMethod` (rule_based / llm_fallback / manual) определён.
- `SectionClassification` frozen=True, extra="forbid".
- `confidence` в [0.0, 1.0].

Зависит от: T-S04-001

---

### T-S04-005. DocumentParseReport + ParseError DTO ✓ ВЫПОЛНЕНО

Target:
- `schemas/setup/parse_report.py`

Acceptance:
- `ParseError` frozen=True с `retryable: bool`.
- `SectionsSummary` с `sections_by_type: dict[str, int]`.
- `DocumentParseReport` с `errors`, `warnings` списками.

Зависит от: T-S04-002, T-S04-003

---

## S1. Repositories (in-memory, Protocol + Lock)

### T-S04-006. ParseJobRepository

Target:
- `src/fe_bot/setup/parser/job_repository.py`
- `tests/unit/test_parse_job_repository.py`

Acceptance:
- `ParseJobRepository(Protocol)` объявляет: `create`, `get`, `update`, `list_for_setup_job`, `get_active_for_setup_job`.
- `InMemoryParseJobRepository` thread-safe (threading.Lock), deep-copy на чтение.
- `create` бросает `DuplicateParseJobError` если `parse_job_id` уже есть.
- `get_active_for_setup_job` возвращает None если нет активного job (status CREATED/QUEUED/RUNNING).
- 6 unit-тестов: create, get, update, list, get_active, concurrent_create_same_id.

Зависит от: T-S04-002

---

### T-S04-007. ParseJobDocumentRepository

Target:
- `src/fe_bot/setup/parser/document_repository.py`
- `tests/unit/test_parse_job_document_repository.py`

Acceptance:
- `ParseJobDocumentRepository(Protocol)`: `add`, `get`, `update`, `list_for_job`, `list_pending_for_job`.
- `InMemoryParseJobDocumentRepository` thread-safe.
- `list_pending_for_job` возвращает только PENDING статус в стабильном порядке.
- 5 unit-тестов.

Зависит от: T-S04-003

---

### T-S04-008. ParsedSectionRepository

Target:
- `src/fe_bot/setup/parser/section_repository.py`
- `tests/unit/test_parsed_section_repository.py`

Acceptance:
- `ParsedSectionRepository(Protocol)`: `save`, `save_batch`, `get`, `list_for_document`, `list_for_job`, `find_by_content_hash`.
- `InMemoryParsedSectionRepository` thread-safe.
- `save_batch` атомарный: либо все сохраняются, либо ни одна (rollback если section_id уже существует).
- `find_by_content_hash` возвращает первую найденную (дедупликация).
- 6 unit-тестов: save, save_batch_atomic, get, list_for_document, list_for_job, find_by_hash.

Зависит от: T-S04-001

---

### T-S04-009. DocumentParseReportRepository

Target:
- `src/fe_bot/setup/parser/report_repository.py`
- `tests/unit/test_parse_report_repository.py`

Acceptance:
- `DocumentParseReportRepository(Protocol)`: `save`, `get`, `get_for_document_in_job`, `list_for_job`.
- `InMemoryDocumentParseReportRepository` thread-safe.
- `get_for_document_in_job(parse_job_id, source_document_id)` возвращает None если нет.
- Unique constraint `(parse_job_id, source_document_id)`: повторный `save` перезаписывает.
- 5 unit-тестов.

Зависит от: T-S04-005

---

## S2. Parser strategies

### T-S04-010. ParserRegistry + стратегия Protocol

Target:
- `src/fe_bot/setup/parser/registry.py`
- `tests/unit/test_parser_registry.py`

Acceptance:
- `ParserStrategy(Protocol)`: `def parse(self, *, source_document_id: str, parse_job_id: str, data: bytes, filename: str) -> list[ParsedSection]`.
- `ParserRegistry` регистрирует стратегии по `ParserStrategy` enum-ключу.
- `get_strategy(content_type: str) -> ParserStrategy`: возвращает стратегию или бросает `UnsupportedFormatError`.
- Content-type маппинг: `text/markdown` → MARKDOWN, `text/plain` → TEXT, `text/csv` → CSV, `application/json` → JSON, `application/pdf` → PDF_TEXT, `...docx` → DOCX, `...xlsx` → XLSX.
- 5 unit-тестов: registration, get_known, get_unknown, override_strategy, list_supported.

Зависит от: T-S04-001, T-S04-002

---

### T-S04-011. MarkdownParserStrategy (адаптация markdown_parser.py)

Target:
- `src/fe_bot/setup/parser/strategies/markdown.py`
- `tests/unit/test_markdown_parser.py` (обновить существующие + добавить новые)
- `tests/fixtures/parser/simple.md`, `tests/fixtures/parser/complex.md`

Acceptance:
- `MarkdownParserStrategy` реализует `ParserStrategy` Protocol.
- Адаптирует `parse_markdown()` из `markdown_parser.py`: принимает `parse_job_id` вместо `setup_job_id`.
- `section_index` заполняется по порядку (0-based).
- `parent_section_id` выставляется корректно: H2 под H1 получает `section_id` родительской H1-секции.
- `heading_path` зеркалит иерархию заголовков (AC-01 из §19).
- YAML front matter сохраняется в `metadata.front_matter`.
- Документ без заголовков → одна секция.
- `structural_payload` содержит `code_blocks: list[str]` если есть ```-блоки.
- 8 unit-тестов: h1h2h3_hierarchy, parent_section_id, no_headings, front_matter, code_blocks, empty_doc_raises, unicode, section_index_sequence.

Зависит от: T-S04-010

---

### T-S04-012. PlainTextParserStrategy + JSON adaptation

Target:
- `src/fe_bot/setup/parser/strategies/plain_text.py`
- `src/fe_bot/setup/parser/strategies/json_parser.py`
- `tests/unit/test_text_json_strategies.py`
- `tests/fixtures/parser/valid.json`

Acceptance:
- `PlainTextParserStrategy`: весь текст → одна секция, `section_type=UNKNOWN`, `confidence=0.7`.
- Адаптирует `parse_plain_text()` из `text_parsers.py` под Protocol.
- `JsonParserStrategy`: top-level ключи → отдельные секции (каждый ключ dict → `section_type=SCHEMA`, `title=key_name`). Если JSON — массив или скаляр → одна секция.
- Обе стратегии принимают `parse_job_id`, заполняют `section_index`.
- `structural_payload` для JSON: `{"json_type": "object", "keys": [...]}`.
- 7 unit-тестов: txt_basic, txt_empty_raises, json_object_keys, json_array_single_section, json_scalar, json_invalid_raises, json_unicode.

Зависит от: T-S04-010

---

### T-S04-013. CSVParserStrategy

Target:
- `src/fe_bot/setup/parser/strategies/csv_parser.py`
- `tests/unit/test_csv_strategy.py`
- `tests/fixtures/parser/tabular.csv`

Acceptance:
- Адаптирует `parse_csv()` из `text_parsers.py`: одна секция на весь файл, `section_type=SCHEMA`.
- `structural_payload` содержит `{"columns": [...], "row_count": N, "preview_rows": [[...]]}`.
- Поддержка BOM (utf-8-sig) и разных разделителей (auto-detect через `csv.Sniffer`).
- Пустой CSV → `ParseFailedError`.
- CSV с только заголовком (0 data rows) → одна секция с `row_count=0`.
- 6 unit-тестов: basic, bom_handling, empty_raises, header_only, sniffer_delimiter, large_file_truncation.

Зависит от: T-S04-010

---

### T-S04-014. PDFParserStrategy (pypdf)

Target:
- `src/fe_bot/setup/parser/strategies/pdf_parser.py`
- `tests/unit/test_pdf_strategy.py`
- `tests/fixtures/parser/text-only.pdf`, `tests/fixtures/parser/scanned.pdf`

Acceptance:
- `PdfParserStrategy` использует `pypdf.PdfReader` для извлечения text layer.
- Каждая страница → отдельная секция; `title=f"Page {page_num}"`, `section_type=UNKNOWN`.
- `metadata.page_number` = номер страницы (1-based) (AC-02 из §19).
- `start_offset` и `end_offset` — символьные offsets в конкатенированном тексте.
- Scanned PDF (text layer пуст) → `ParseErrorCode.PDF_TEXT_LAYER_NOT_FOUND`, секции не создаются.
- `structural_payload` содержит `{"page_count": N}` для всех страниц (добавляется в metadata первой секции).
- 7 unit-тестов: single_page, multi_page, scanned_raises_correct_code, page_numbers_in_metadata, empty_page_skipped, unicode_pdf, offsets_sequence.

Зависит от: T-S04-010

---

### T-S04-015. DOCXParserStrategy (python-docx)

Target:
- `src/fe_bot/setup/parser/strategies/docx_parser.py`
- `tests/unit/test_docx_strategy.py`
- `tests/fixtures/parser/complex.docx`

Acceptance:
- `DocxParserStrategy` использует `python_docx.Document` для чтения.
- Параграфы со стилем `Heading 1/2/3` → границы секций (аналог Markdown H1/H2/H3).
- `parent_section_id` выставляется аналогично MarkdownParserStrategy (иерархия стилей).
- Таблицы DOCX → `structural_payload.tables: list[list[list[str]]]` (матрица ячеек).
- Corrupted DOCX → `ParseErrorCode.DOCX_EXTRACTION_FAILED`.
- `section_index` заполняется.
- 7 unit-тестов: heading_hierarchy, table_in_payload, corrupted_raises, no_headings_single_section, parent_section_id, unicode_content, heading_path.

Зависит от: T-S04-010

---

### T-S04-016. XLSXParserStrategy (openpyxl)

Target:
- `src/fe_bot/setup/parser/strategies/xlsx_parser.py`
- `tests/unit/test_xlsx_strategy.py`
- `tests/fixtures/parser/multi-sheet.xlsx`

Acceptance:
- `XlsxParserStrategy` использует `openpyxl.load_workbook(read_only=True)`.
- Каждый sheet → отдельная секция; `title=sheet_name`, `section_type=SCHEMA`.
- `structural_payload`: `{"sheet_name": ..., "columns": [...], "row_count": N, "preview_rows": [[...]]}`.
- `max_rows_per_sheet=500` — truncation с `warning` в `DocumentParseReport.warnings`.
- Пустой sheet → секция с `section_status=IGNORED`.
- `metadata.sheet_names` = список всех листов книги.
- 6 unit-тестов: single_sheet, multi_sheet_sections, empty_sheet_ignored, truncation_warning, sheet_names_in_metadata, corrupted_raises.

Зависит от: T-S04-010

---

## S3. SectionBoundaryDetector + SectionClassifier

### T-S04-017. SectionBoundaryDetector

Target:
- `src/fe_bot/setup/parser/boundary.py`
- `tests/unit/test_section_boundary.py`

Acceptance:
- `SectionBoundaryDetector.detect(raw_text: str, strategy: ParserStrategy) -> list[SectionBoundary]`.
- `SectionBoundary(start: int, end: int, title: str, level: int)`.
- Для Markdown: regex по `^#{1,3}` (уже в `markdown_parser.py` — вынести логику сюда).
- Для DOCX: делегирует определение heading-позиций стратегии (через `structural_payload`).
- Для PDF/TXT/CSV/JSON: возвращает единственный boundary `[0, len(text)]`.
- 6 unit-тестов: markdown_headings, docx_heading_styles, pdf_single_boundary, txt_single, csv_single, json_top_keys.

Зависит от: T-S04-010

---

### T-S04-018. SectionClassifier (rule-based)

Target:
- `src/fe_bot/setup/parser/classifier.py`
- `tests/unit/test_section_classifier.py`

Acceptance:
- `SectionClassifier.classify(section: ParsedSection) -> SectionClassification`.
- Rule-based: keyword matching по `title + raw_text[:500]`.
- Keyword → SectionType маппинг: task/задач → TASK, schema/схем → SCHEMA, analytics/аналитик → ANALYTICS, glossary/глоссарий → GLOSSARY, validation/валидаци → VALIDATION_RULE, question/вопрос → QUESTION_TEMPLATE, feature/признак → TASK.
- `confidence` = 0.9 если совпадение в title, 0.7 если только в тексте, 0.5 если нет совпадений → `SectionType.UNKNOWN`.
- LOW_CONFIDENCE threshold = `< confidence_threshold` (default 0.7).
- `ClassificationMethod.RULE_BASED` всегда.
- `reason` = описание сработавшего правила (какое keyword, где).
- 8 unit-тестов: keyword_in_title_high_confidence, keyword_in_text_medium, no_match_unknown, multiple_keywords_highest_wins, case_insensitive, confidence_threshold_low, russian_keyword, english_keyword.

Зависит от: T-S04-004, T-S04-001

---

## S4. DocumentParserOrchestrator + SourceLifecycle integration

### T-S04-019. ParseJob events (EventBus)

Target:
- `src/fe_bot/setup/parser/events.py`
- `tests/unit/test_parse_events.py`

Acceptance:
- `ParseJobEvent(BaseModel)` base с `event_id`, `parse_job_id`, `setup_job_id`, `occurred_at`.
- 10 конкретных event-классов: `ParseJobCreatedEvent`, `ParseJobStartedEvent`, `ParseJobCompletedEvent`, `ParseJobFailedEvent`, `ParseJobPartialSuccessEvent`, `ParseDocumentStartedEvent`, `ParseDocumentCompletedEvent`, `ParseDocumentFailedEvent`, `ParsedSectionsCreatedEvent`, `SectionClassificationLowConfidenceEvent`.
- Все event-классы frozen=True, extra="forbid".
- `ParsedSectionsCreatedEvent` содержит `section_ids: list[str]`, `sections_count: int`.
- `SectionClassificationLowConfidenceEvent` содержит `section_id`, `confidence`, `candidate_type`.
- 5 unit-тестов: instantiation каждого event, payload validation.

Зависит от: T-S04-002

---

### T-S04-020. DocumentParserOrchestrator

Target:
- `src/fe_bot/setup/parser/orchestrator.py`
- `tests/component/test_document_parser_orchestrator.py`

Acceptance:
- `DocumentParserOrchestrator.__init__` принимает: `ParseJobRepository`, `ParseJobDocumentRepository`, `ParsedSectionRepository`, `DocumentParseReportRepository`, `ParserRegistry`, `SectionBoundaryDetector`, `SectionClassifier`, `SourceRegistryService`, `EventBus`.
- `create_parse_job(setup_job_id, requested_by, config) -> ParseJob`: создаёт ParseJob (status=CREATED), вызывает `SourceRegistryService.update_status(WAITING_FOR_PARSING)` для всех eligible документов, эмиттит `ParseJobCreatedEvent`.
- `run(parse_job_id) -> ParseJob`: переводит в RUNNING, последовательно обрабатывает каждый документ, при завершении вычисляет итоговый статус (COMPLETED / PARTIAL_SUCCESS / FAILED), эмиттит соответствующий event.
- Per-document: `update_status(PARSING)` → dispatch strategy → save sections → classify → save report → `update_status(SECTIONS_EXTRACTED / PARSE_FAILED)` → emit events.
- Если confidence < threshold → `SectionClassificationLowConfidenceEvent` + `section_status=LOW_CONFIDENCE`.
- `PARSE_JOB_ALREADY_RUNNING` если существует активный job для setup_job_id.
- 8 component-тестов: create_job, run_single_doc, run_multi_doc, partial_success_on_one_fail, already_running_raises, source_lifecycle_called, events_emitted, low_confidence_event.

Зависит от: T-S04-006 через T-S04-009, T-S04-010, T-S04-017, T-S04-018, T-S04-019

---

### T-S04-021. SourceLifecycle integration + lineage

Target:
- `src/fe_bot/setup/parser/orchestrator.py` (дополнение)
- `tests/integration/test_parser_source_lifecycle.py`

Acceptance:
- После успешного парсинга документа вызывается `SourceRegistryService.link_artifact(target_type=PARSED_SECTION, target_id=section_id, relation_type=PARSED_FROM)` для каждой секции.
- `SourceRegistryService.append_processing_log(step=PARSING, level=INFO/ERROR)` для каждого документа (SUCCESS или FAIL с `error_code`).
- Если документ в несовместимом статусе (не `WAITING_FOR_PARSING`) → `skip` с `SKIPPED` ParseJobDocument-статусом, лог WARNING.
- 5 integration-тестов: lineage_created_per_section, processing_log_info_on_success, processing_log_error_on_fail, incompatible_status_skipped, sections_extracted_status_set.

Зависит от: T-S04-020, SETUP-03 SourceRegistryService (T-S03-010)

---

### T-S04-022. Parse metrics + structured logging

Target:
- `src/fe_bot/setup/parser/orchestrator.py` (dI MetricsRegistry + StructuredLogger)
- `tests/integration/test_parse_metrics.py`

Acceptance:
- 4 метрики через `MetricsRegistry`: `parse_documents_total{format,outcome}` (Counter), `parse_duration_seconds{format}` (Histogram), `parse_sections_total{section_type,confidence_bucket}` (Counter), `parse_job_failures_total{error_code}` (Counter).
- Structured log каждого parsed document: `{parse_job_id, source_document_id, format, sections_count, duration_ms, outcome}`.
- `confidence_bucket` = `high` (>=0.9) / `medium` (0.7..0.9) / `low` (<0.7).
- 4 integration-тестов: document_counter_incremented, duration_histogram, sections_counter_by_type, failure_counter_by_error_code.

Зависит от: T-S04-020

---

## S5. API endpoints + permissions

### T-S04-023. kb.parse.* permissions + POST /parse-jobs

Target:
- `src/fe_bot/auth/permissions.py` (добавить 5 новых Permission)
- `src/fe_bot/api/setup/parse_router.py` (новый файл)
- `tests/unit/test_auth_permissions.py` (обновить)
- `tests/integration/test_create_parse_job.py`

Acceptance:
- 5 новых Permission: `KB_PARSE_RUN = "kb.parse.run"`, `KB_PARSE_STATUS_READ = "kb.parse.status.read"`, `KB_SECTION_READ = "kb.section.read"`, `KB_PARSE_RETRY = "kb.parse.retry"`, `KB_PARSE_CANCEL = "kb.parse.cancel"`.
- Роль → permission матрица: USER (run, status_read, section_read), DOMAIN_EXPERT (+ retry), RAG_ADMIN (все), AUDITOR (status_read, section_read).
- `POST /api/v1/setup/{setup_job_id}/parse-jobs` (KB_PARSE_RUN): создаёт ParseJob, возвращает `ParseJobResponse`.
- Response: `parse_job_id`, `status`, `total_documents`, `created_at`.
- `409 PARSE_JOB_ALREADY_RUNNING` если активный job существует.
- 6 integration-тестов: happy_path, 409_already_running, 403_no_permission, 404_setup_job, 400_no_parseable_docs, response_shape.

Зависит от: T-S04-020

---

### T-S04-024. GET /parse-jobs/{id} + GET /parse-jobs/{id}/report

Target:
- `src/fe_bot/api/setup/parse_router.py`
- `tests/integration/test_parse_job_status.py`

Acceptance:
- `GET /api/v1/setup/{setup_job_id}/parse-jobs/{parse_job_id}` (KB_PARSE_STATUS_READ): возвращает полный `ParseJobResponse` с progress counters и timing.
- `GET /api/v1/setup/{setup_job_id}/parse-jobs/{parse_job_id}/report` (KB_PARSE_STATUS_READ): возвращает `ParseJobReportResponse` — список `DocumentParseReport` для всех документов с ошибками и warnings.
- `404` если `parse_job_id` не найден или не принадлежит `setup_job_id`.
- Cross-job isolation: parse_job из другого setup_job → 404.
- 7 integration-тестов: status_created, status_running_with_progress, status_completed, report_with_errors, report_empty, 404_unknown, 404_cross_job.

Зависит от: T-S04-023

---

### T-S04-025. GET /parse-jobs/{id}/sections + POST /parse-jobs/{id}/cancel

Target:
- `src/fe_bot/api/setup/parse_router.py`
- `tests/integration/test_parse_sections_endpoint.py`
- `tests/integration/test_cancel_parse_job.py`

Acceptance:
- `GET /api/v1/setup/{setup_job_id}/parse-jobs/{parse_job_id}/sections` (KB_SECTION_READ): возвращает paginated список `ParsedSectionResponse`.
  - Query params: `?source_document_id=`, `?section_type=`, `?status=`, `?page=`, `?page_size=`.
  - `ParsedSectionResponse` включает `section_id`, `title`, `section_type`, `section_status`, `confidence`, `heading_path`, `section_index`, `parent_section_id`, `content_hash` (не raw_text в list mode).
- `POST /api/v1/setup/{setup_job_id}/parse-jobs/{parse_job_id}/cancel` (KB_PARSE_CANCEL): переводит RUNNING/QUEUED → CANCELLED. Terminal job → 409.
- 8 integration-тестов: sections_list, sections_filter_by_type, sections_filter_by_doc, sections_pagination, sections_403, cancel_running, cancel_terminal_409, cancel_404.

Зависит от: T-S04-024

---

### T-S04-026. POST /parse-jobs/{id}/documents/{doc_id}/retry

Target:
- `src/fe_bot/api/setup/parse_router.py`
- `src/fe_bot/setup/parser/orchestrator.py` (метод `retry_document`)
- `tests/integration/test_parse_retry.py`

Acceptance:
- `POST /api/v1/setup/{setup_job_id}/parse-jobs/{parse_job_id}/documents/{source_document_id}/retry` (KB_PARSE_RETRY).
- Только если `ParseJobDocumentStatus.FAILED` → сбрасывает до `PENDING`, создаёт новый `ParseJobDocument`, re-парсирует документ.
- Не FAILED → 409 `DOCUMENT_NOT_PARSEABLE_STATUS`.
- Успешный retry → обновляет ParseJob.failed_documents--, processed_documents++.
- Если ParseJob уже terminal (COMPLETED/FAILED) → retry создаёт новый ParseJob для одного документа.
- `audit` event `PARSE_RETRY_TRIGGERED`.
- 6 integration-тестов: retry_failed_doc, retry_non_failed_409, retry_in_terminal_job_creates_new_job, retry_updates_counters, 404_unknown_doc, 403.

Зависит от: T-S04-025

---

## S6. Frontend (6 компонентов)

### T-S04-027. API client + TypeScript types для Parse

Target:
- `frontend/src/api/types.ts` (расширить)
- `frontend/src/api/parse.ts` (новый файл)
- `frontend/src/test/msw.ts` (MSW handlers для 6 endpoints)
- `frontend/src/api/__tests__/parse.test.ts`

Acceptance:
- TypeScript типы: `ParseJob`, `ParseJobStatus`, `ParsedSection`, `ParsedSectionStatus`, `SectionType`, `DocumentParseReport`, `ParseError`, `ParseJobDocumentStatus`.
- 6 API функций: `createParseJob`, `getParseJobStatus`, `getParseJobReport`, `listParsedSections`, `cancelParseJob`, `retryParseDocument`.
- MSW handlers для всех 6 endpoints с mock data.
- `npm run typecheck` чистый.
- 6 unit-тестов: каждая функция вызывает правильный endpoint, response типизирован.

Зависит от: T-S04-023 через T-S04-026

---

### T-S04-028. ParseJobProgressPanel + SectionTreeView

Target:
- `frontend/src/components/Parsing/ParseJobProgressPanel.tsx`
- `frontend/src/components/Parsing/SectionTreeView.tsx`
- `frontend/src/components/Parsing/__tests__/ParseJobProgressPanel.test.tsx`
- `frontend/src/components/Parsing/__tests__/SectionTreeView.test.tsx`

Acceptance:
- `ParseJobProgressPanel`: per-document progress bars (processing / completed / failed), итоговые counters (total / processed / failed / sections), кнопка Cancel (только если status=RUNNING/QUEUED).
- `SectionTreeView`: иерархическое дерево секций (heading_path + parent_section_id), badge `section_type`, цветной индикатор `confidence` (high/medium/low), фильтр по `section_type`.
- Polling каждые 2s если status=RUNNING (через `useInterval`).
- 8 unit-тестов: progress_counters, cancel_button_visible, cancel_button_hidden_terminal, tree_hierarchy, type_badge, confidence_indicator, filter_by_type, polling_stops_on_terminal.

Зависит от: T-S04-027

---

### T-S04-029. ParseReportDrawer + WizardParsingStep integration

Target:
- `frontend/src/components/Parsing/ParseReportDrawer.tsx`
- `frontend/src/components/Wizard/steps/ParsingStep.tsx` (новый шаг мастера)
- `frontend/src/components/Parsing/__tests__/ParseReportDrawer.test.tsx`
- `frontend/src/components/Parsing/__tests__/ParsingStep.test.tsx`

Acceptance:
- `ParseReportDrawer`: список ошибок из `DocumentParseReport.errors` с `error_code` + `message` + `retryable` badge, список warnings, кнопка "Retry" для retryable ошибок (вызывает `retryParseDocument`).
- `ParsingStep`: встраивается в Wizard после UploadDocumentsStep. Кнопка "Start Parsing" → `createParseJob`. Отображает `ParseJobProgressPanel`. После COMPLETED/PARTIAL_SUCCESS → кнопка "View Sections" открывает `SectionTreeView`. При FAILED → "View Report" открывает `ParseReportDrawer`.
- 6 unit-тестов: report_errors_list, retryable_badge, retry_button_calls_api, step_start_button, step_transitions, step_view_sections.

Зависит от: T-S04-028

---

## S7. Resilience + Audit + Docs

### T-S04-030. Resilience tests

Target:
- `tests/integration/test_parse_resilience.py`
- `tests/unit/test_parse_state_machine.py`

Acceptance:
- **ParseJob state machine**: 5 invalid transitions → `InvalidParseJobTransitionError`, 6 valid transitions → success.
- **Storage down**: `ArtifactStorage.download` raises → секция не создаётся, `ParseJobDocument.status=FAILED`, ParseJob → `PARTIAL_SUCCESS` (если другие документы успешны).
- **Malformed file**: corrupted PDF/DOCX → `ParseErrorCode.TEXT_EXTRACTION_FAILED` или `DOCX_EXTRACTION_FAILED`, не Exception.
- **Parse timeout** (симулируется mock sleep): `ParseErrorCode.PARSE_TIMEOUT`, `retryable=True`.
- **Idempotency**: повторный `createParseJob` при существующем RUNNING → 409, при terminal → новый job.
- **Concurrent jobs**: 2 одновременных `create_parse_job` для одного `setup_job_id` → один получает 409.
- **Cancel during parse**: RUNNING → CANCELLED → текущий документ дочитывается, новые не начинаются.
- **Content_hash deduplication**: одна и та же секция (content_hash) не дублируется при retry.
- 12 resilience-тестов покрывают все сценарии.

Зависит от: T-S04-026

---

### T-S04-031. Audit events + final verify

Target:
- `src/fe_bot/audit/service.py` (новые `AuditAction`)
- `src/fe_bot/setup/parser/orchestrator.py` (audit hooks)
- `tests/integration/test_parse_audit.py`

Acceptance:
- Новые `AuditAction`: `PARSE_JOB_CREATED`, `PARSE_JOB_STARTED`, `PARSE_JOB_COMPLETED`, `PARSE_JOB_FAILED`, `PARSE_JOB_CANCELLED`, `PARSE_RETRY_TRIGGERED`.
- Каждый audit event пишется с `{parse_job_id, setup_job_id, user_id, outcome}`.
- 6 audit-тестов: один per AuditAction.
- Финальный verify: `pytest tests/` → все проходят (ожидается ~900+ тестов), `mypy --strict` → 0 errors, `ruff check` → 0 errors, `npm run typecheck && npm test && npm run build` → green.

Зависит от: T-S04-030

---

### T-S04-032. Documentation + traceability update

Target:
- `docs/02-system/features/SETUP-04-document-parsing.md` (заменить placeholder на полную спеку)
- `docs/traceability/setup-04.md` (новый — 48 AC → impl → tests + 30 tasks → files → tests + 6 endpoints + 10 events)
- `docs/traceability/coverage-matrix.md` (добавить строку SETUP-04)
- `docs/implementation-plan/README.md` (добавить SETUP-04)

Acceptance:
- Все 48 AC из §19 спека трассированы к конкретному файлу и тесту.
- Все 30 tasks трассированы к target files.
- 6 endpoints с permission матрицей задокументированы.
- 10 events задокументированы.
- Документация на русском.

Зависит от: T-S04-031

---

## Acceptance Gate SETUP-04

```text
✓ pytest tests/               → ~900+ тестов, все pass
✓ mypy --strict schemas/ validators/ src/   → 0 errors
✓ ruff check schemas/ validators/ src/ tests/  → 0 errors
✓ npm run typecheck + npm test + npm run build  → green
✓ Все 48 AC из §19             → трассированы к тестам
✓ 7 форматов парсятся         → unit-тест каждого
✓ ParseJob state machine       → 11 переходов покрыты
✓ 6 API endpoints              → contract-тесты OpenAPI
✓ 10 events эмиттятся          → integration-тесты
✓ 4 метрики регистрируются     → integration-тесты
✓ SETUP-01/02/03 регрессия     → 859+ старых тестов pass
```

---

## Прогресс summary

```
S0 ✓ 5/5  S1 ○ 0/4  S2 ○ 0/7  S3 ○ 0/2  S4 ○ 0/4  S5 ○ 0/4  S6 ○ 0/3  S7 ○ 0/3
5/30 задач (17%) — S0 полностью выполнен в текущей сессии
```

## Зависимости от других фич

- SETUP-01 ✓ closed (auth, permissions, audit, metrics, EventBus)
- SETUP-02 ✓ closed (upload flow, SourceDocument schema, ArtifactStorage)
- SETUP-03 ✓ closed (SourceRegistryService с update_status, link_artifact, append_processing_log)
- INF-002 (PostgreSQL миграции) — отложено; репозитории in-memory
- INF-004 (pypdf, python-docx, openpyxl в pyproject.toml) — добавить зависимости в T-S04-014..016
