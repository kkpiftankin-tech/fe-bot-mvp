# План реализации MVP FE-Bot

Нумерованный список задач, упорядоченных по зависимостям. Каждая задача ссылается на docs, schemas и тесты, которые она трогает. Шаблон — в [../00-methodology/artifact-templates.md](../00-methodology/artifact-templates.md#задача-реализации-docsimplementation-planplantasksmd).

## Фундамент: контракты и валидаторы

### T-PL-001. ContextMemory schema

Target:
- `schemas/context_memory.py`
- `tests/unit/test_context_memory_schema.py`

Acceptance:
- Pydantic-схема валидирует минимальное и полное состояние.
- Невалидная `current_phase` отвергается.
- Сумма `class_distribution.priors` валидируется.
- При откате фазы downstream-слоты инвалидируются (метод `invalidate_downstream(from_phase)`).

### T-PL-002. RAG metadata validator

Target:
- `validators/rag_metadata_validator.py`
- `tests/unit/test_rag_metadata_validator.py`

Acceptance:
- `doc_id` обязателен.
- `doc_type` ∈ онтологии.
- `phase`, `retrieval_tags` валидируются.
- `chunk_id` уникален в рамках kb_version.

### T-PL-003. FeatureSpec schema + validator

Target:
- `schemas/feature_spec.py`
- `validators/feature_validator.py`
- `tests/unit/test_feature_validator.py`

Acceptance:
- Все правила из [docs/07-contracts/feature-spec.md](../07-contracts/feature-spec.md) форсятся.
- Безопасный formula-evaluator реализован.
- Temporal-rule, evidence-rule, input-feature-existence-rule покрыты тестами.

### T-PL-004. GenerationSpec schema + validator

Target:
- `schemas/generation_spec.py`
- `validators/generation_spec_validator.py`
- `tests/unit/test_generation_spec_schema.py`
- `tests/unit/test_generation_spec_validator.py`

Acceptance:
- Сумма priors валидируется.
- Производные spec ссылаются на существующие base.
- Temporal-distributions запрещены при `temporal_importance=false`.

### T-PL-005. ValidationReport schema

Target:
- `schemas/validation_report.py`
- `tests/unit/test_validation_report_schema.py`

Acceptance:
- Все коды из [docs/07-contracts/validation-report.md](../07-contracts/validation-report.md) есть в Enum.

### T-PL-006. ExportManifest schema + validator

Target:
- `schemas/export_manifest.py`
- `validators/export_manifest_validator.py`
- `tests/unit/test_export_manifest_validator.py`

Acceptance:
- Отсутствие любого из 9 артефактов даёт `EXPORT_001_MISSING_ARTIFACT`.

## Стадия Setup

### T-SETUP-001. Document upload + Source Registry

Target:
- `src/fe_bot/setup/upload.py`
- `src/fe_bot/setup/source_registry.py`
- `schemas/setup.py` (`UploadedDocument`, `SourceDocument`)
- `tests/component/test_setup_document_upload.py`

Acceptance:
- Дедуп по checksum работает.
- Поддерживаемые типы фильтруются.
- Статус-переходы видны через API.

### T-SETUP-002. Document parsing

Target:
- `src/fe_bot/setup/parser/__init__.py`, `markdown.py`, `pdf.py`, `docx.py`, `csv.py`, `json_parser.py`
- `tests/component/test_setup_parser.py`

Acceptance:
- Markdown по H1/H2/H3 даёт корректное дерево секций.
- PDF сохраняет page numbers.

### T-SETUP-003. RAG Card Generator

Target:
- `src/fe_bot/rag/card_generator.py`
- `prompts/setup_card_generator.md`
- `tests/component/test_setup_card_generation.py`
- `tests/prompt_eval/setup_card_generation_cases.yaml`

Acceptance:
- На эталонной секции эмитит карточку, проходящую `rag_metadata_validator`.
- low-confidence карточки помечаются `review_required`.

### T-SETUP-004. Card review UI + API

Target:
- `src/fe_bot/api/setup/cards.py`
- `tests/component/test_setup_card_review.py`

Acceptance:
- Действия Approve/Reject/Edit/Regenerate работают.
- Каждая правка — новая версия; история сохраняется.

### T-SETUP-005. Chunking + Embedding + Indexer

Target:
- `src/fe_bot/rag/chunking.py`
- `src/fe_bot/rag/embedding.py`
- `src/fe_bot/rag/indexer.py`
- `tests/component/test_setup_chunking.py`
- `tests/component/test_setup_embedding_indexing.py`

Acceptance:
- chunk_id стабилен.
- Vector index создаётся под новой kb_version, неактивен до публикации.

### T-SETUP-006. Retrieval evaluation + Publication

Target:
- `src/fe_bot/rag/evaluation.py`
- `src/fe_bot/setup/publication.py`
- `tests/rag_eval/test_setup_retrieval_smoke.py`
- `tests/e2e/test_setup_wizard_happy_path.py`
- `tests/e2e/test_setup_publish.py`

Acceptance:
- Падающий eval блокирует публикацию.
- После публикации Runtime разблокирован, активная kb_version меняется.

## Стадия Runtime

### T-MA-001. SessionAgent + Conversation persistence

Target:
- `src/fe_bot/agents/session.py`
- `src/fe_bot/persistence/conversations.py`
- `tests/component/test_session_agent.py`

Acceptance:
- Старт сессии требует активной kb_version.
- Resume по conversation_id работает.

### T-MA-002. NLU Agent

Target:
- `src/fe_bot/agents/nlu.py`
- `prompts/nlu_agent.md`
- `tests/component/test_nlu_agent.py`
- `tests/prompt_eval/nlu_agent_cases.yaml`

Acceptance:
- ≥85 % intent accuracy на eval-сьюте.
- ≥80 % entity accuracy.
- `unknown` intent эмитит clarification.

### T-MA-003. RAG Retrieval Agent + Evidence Pack Builder

Target:
- `src/fe_bot/rag/retrieval_planner.py`
- `src/fe_bot/rag/retriever.py`
- `src/fe_bot/rag/evidence_assembler.py`
- `tests/component/test_rag_retrieval_agent.py`

Acceptance:
- Retrieval-политики из [docs/06-rag/retrieval-policies.md](../06-rag/retrieval-policies.md) реализованы.
- EvidencePack укладывается в бюджет.

### T-MA-004. TaskDiscoveryAgent

Target:
- `src/fe_bot/agents/task_discovery.py`
- `prompts/task_discovery_agent.md`
- `tests/component/test_task_discovery_agent.py`

Acceptance:
- Все обязательные слоты заполняются для radar-сценария.
- Missing slots порождают targeted clarification.

### T-MA-005. DataProfilingAgent

Target:
- `src/fe_bot/agents/data_profiling.py`
- `prompts/data_profiling_agent.md`
- `tests/component/test_data_profiling_agent.py`

Acceptance:
- Нормализация `РЛС/radar` работает.
- `temporal_importance=true` требует `timestamp`+`entity_id`.

### T-MA-006. DomainContextAgent

Target:
- `src/fe_bot/agents/domain_context.py`
- `prompts/domain_context_agent.md`
- `tests/component/test_domain_context_agent.py`

Acceptance:
- При 0 `domain_profile`-карточек — `need_more_context=true`, не выдумывает.

### T-MA-007. FeatureSynthesisAgent + FeatureCriticAgent

Target:
- `src/fe_bot/agents/feature_synthesis.py`
- `src/fe_bot/agents/feature_critic.py`
- `prompts/feature_synthesis_agent.md`, `prompts/feature_critic_agent.md`
- `tests/component/test_feature_synthesis_agent.py`, `tests/component/test_feature_critic_agent.py`
- `tests/prompt_eval/feature_synthesis_agent_cases.yaml`

Acceptance:
- На radar-сценарии 19 признаков; все с evidence.
- При temporal_importance=false временные признаки отвергаются.

### T-MA-008. MulticollinearityAgent

Target:
- `src/fe_bot/agents/multicollinearity.py`
- `tests/component/test_multicollinearity_agent.py`

Acceptance:
- VIF + парные корреляции считаются.
- Не отвергает признаки самостоятельно — только рекомендует.

### T-MA-009. DataGenerationSpecAgent

Target:
- `src/fe_bot/agents/generation_spec.py`
- `prompts/generation_spec_agent.md`
- `tests/component/test_data_generation_spec_agent.py`

Acceptance:
- Эмитит spec без строк данных.
- Repair-loop на validation-failure работает.

### T-MA-010. DataGenerationWorker

Target:
- `src/fe_bot/data_generation/generator.py`
- `validators/generated_data_validator.py`
- `tests/component/test_data_generation_worker.py`
- `tests/integration/test_data_generation_flow.py`

Acceptance:
- Для эталонного spec выдаёт `100000 × 19`.
- Перезапуск с тем же seed = байт-идентичный X+y.
- Class balance в пределах ±1 %.

### T-MA-011. ModelSelectionAgent

Target:
- `src/fe_bot/agents/model_selection.py`
- `prompts/model_selection_agent.md`
- `tests/component/test_model_selection_agent.py`

Acceptance:
- Для radar-сценария top-1 — XGBoostClassifier.
- training_config.metrics включает f1_macro.

### T-MA-012. ExportAgent + Export Service

Target:
- `src/fe_bot/agents/export.py`
- `src/fe_bot/export/service.py`
- `tests/component/test_export_agent.py`
- `tests/e2e/test_export_happy_path.py`

Acceptance:
- archive.zip содержит 9 артефактов.
- pipeline.py импортирует только разрешённые библиотеки.

### T-MA-013. FeedbackAgent + Human review controller

Target:
- `src/fe_bot/agents/feedback.py`
- `src/fe_bot/runtime/human_review.py`
- `tests/component/test_feature_review.py`

Acceptance:
- restart создаёт новый conversation.
- Rollback инвалидирует downstream-слоты.

### T-MA-014. AuditAgent + Audit Service

Target:
- `src/fe_bot/agents/audit.py`
- `src/fe_bot/observability/audit_service.py`
- `schemas/audit.py`
- `tests/component/test_audit_agent.py`
- `tests/e2e/test_audit_trail.py`

Acceptance:
- Append-only; цепочка от source до archive строится.
- Экспорт audit-цепочки в JSON работает.

## Платформа

### T-PL-010. FastAPI backend + auth

Target:
- `src/fe_bot/api/main.py`
- `src/fe_bot/api/setup/*`, `src/fe_bot/api/runtime/*`, `src/fe_bot/api/analytics/*`
- `tests/integration/test_api_contracts.py`

Acceptance:
- Все эндпоинты с Pydantic-телами.
- Унифицированный error-envelope.

### T-PL-011. LangGraph orchestrator wiring

Target:
- `src/fe_bot/graph/build_graph.py`
- `src/fe_bot/graph/nodes/`
- `tests/integration/test_langgraph_state_machine.py`

Acceptance:
- Узлы и edges из [docs/09-langgraph/edges.md](../09-langgraph/edges.md) проходят.
- Repair-loops с `max_retries=3` работают.

### T-PL-012. Artifact Storage + Download Manager

Target:
- `src/fe_bot/export/storage.py`
- `src/fe_bot/api/runtime/downloads.py`
- `tests/integration/test_artifact_download.py`

Acceptance:
- Conversation-scoped URL'ы с TTL.
- Истёкший URL возвращает 410.

## Аналитика и observability

### T-OBS-001. Структурированные логи

Target:
- `src/fe_bot/observability/logging.py`

Acceptance:
- JSON-формат с обязательными полями из [docs/11-operations/observability.md](../11-operations/observability.md).

### T-OBS-002. Prometheus метрики

Target:
- `src/fe_bot/observability/metrics.py`
- `tests/component/test_metrics_exposition.py`

Acceptance:
- Все метрики из [docs/11-operations/metrics.md](../11-operations/metrics.md) экспонируются.

### T-AN-001. Analytics endpoints

Target:
- `src/fe_bot/api/analytics/*`
- `tests/component/test_session_funnel_analytics.py` и т. д.

Acceptance:
- Эндпоинты для всех 9 ANALYTICS-фич отвечают.

## E2E

### T-E2E-001. Setup happy path

Target:
- `tests/e2e/test_setup_wizard_happy_path.py`
- `tests/e2e/test_setup_publish.py`

Acceptance:
- Корпус radar-документов проходит от загрузки до публикации KB за один запуск.

### T-E2E-002. Runtime happy path

Target:
- `tests/e2e/test_runtime_happy_path.py`

Acceptance:
- Эталонный radar-сценарий доходит до archive.zip.
- Метаданные содержат корректные digests.

### T-E2E-003. Audit trail

Target:
- `tests/e2e/test_audit_trail.py`

Acceptance:
- Цепочка от source-PDF до archive-артефакта восстанавливается.

## Готовность MVP

MVP считается готовым, когда зелёные:

- `make test-unit`
- `make test-component`
- `make test-prompt`
- `make test-rag`
- `make test-integration`
- `make test-e2e`
- `make smoke`

И traceability-матрицы заполнены по всем фичам реестра.
