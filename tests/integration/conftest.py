"""Shared fixtures для integration-тестов API."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fe_bot.api.dependencies import (
    _artifact_storage,
    _card_registry,
    _event_bus,
    _job_repository,
    _orchestrator,
    _source_registry,
    get_artifact_storage,
    get_audit_log,
    get_audit_service,
    get_batch_registry,
    get_card_registry,
    get_card_review,
    get_evaluation_service,
    get_event_bus,
    get_idempotency_cache,
    get_job_repository,
    get_kb_publish_service,
    get_kb_repository,
    get_lineage_repo,
    get_metadata_validation,
    get_metrics,
    get_orchestrator,
    get_orphan_cleanup_service,
    get_parser_service,
    get_pipeline,
    get_processing_log_repo,
    get_retrieval_service,
    get_source_lifecycle,
    get_source_registry,
    get_status_history_repo,
    get_upload_service,
    get_vector_index_client,
    get_vector_indexer,
)
from fe_bot.app import create_app
from fe_bot.audit.service import AuditService, InMemoryAuditLog
from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.retrieval.service import RetrievalService
from fe_bot.setup.card_generator.service import (
    RAGCardFallbackGenerator,
    RAGCardGenerator,
)
from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry
from fe_bot.setup.card_review.service import RAGCardReviewService
from fe_bot.setup.chunking.service import ChunkingService
from fe_bot.setup.embedding.service import EmbeddingService
from fe_bot.setup.evaluation.service import RAGEvaluationService
from fe_bot.setup.events import EventBus
from fe_bot.setup.metadata_validation.service import MetadataValidationService
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.parser.service import DocumentParserService
from fe_bot.setup.pipeline import SetupPipeline
from fe_bot.setup.publish.service import (
    InMemoryKBRepository,
    KBPublishService,
)
from fe_bot.setup.repository import InMemoryJobRepository
from fe_bot.setup.source_registry.lifecycle import SourceLifecycleService
from fe_bot.setup.source_registry.lineage import InMemoryLineageRepository
from fe_bot.setup.source_registry.processing_log import (
    InMemoryProcessingLogRepository,
)
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.setup.source_registry.status_history import (
    InMemoryStatusHistoryRepository,
)
from fe_bot.setup.upload.batch_registry import InMemoryBatchRegistry
from fe_bot.setup.upload.cleanup import OrphanCleanupService
from fe_bot.setup.upload.idempotency import InMemoryIdempotencyCache
from fe_bot.setup.upload.service import DocumentUploadService
from fe_bot.storage.artifact_service import InMemoryArtifactStorage
from fe_bot.vector_index.client import InMemoryVectorIndexClient
from fe_bot.vector_index.service import VectorIndexerService


@pytest.fixture
def app_with_clean_state() -> FastAPI:
    """FastAPI app с чистым in-memory state на каждый тест.

    Pipeline использует fallback card generator (без LLM) — integration-тесты
    не должны ходить в Ollama. Полноценный тест LLM-режима — в test_run_pipeline.py
    через respx mocks.
    """
    app = create_app()
    repo = InMemoryJobRepository()
    bus = EventBus()
    orchestrator = SetupOrchestrator(repo, bus)
    storage = InMemoryArtifactStorage()
    registry = InMemorySourceRegistry()
    # S8 observability сначала — DocumentUploadService принимает их (T-S02-011/012).
    audit_log = InMemoryAuditLog()
    audit_svc = AuditService(audit_log)
    metrics_registry = MetricsRegistry()
    # SETUP-03 / T-S03-019: lifecycle service для auto registration after upload.
    status_history_repo = InMemoryStatusHistoryRepository()
    processing_log_repo = InMemoryProcessingLogRepository()
    lineage_repo = InMemoryLineageRepository()
    source_lifecycle = SourceLifecycleService(
        registry=registry,
        status_history=status_history_repo,
        processing_log=processing_log_repo,
        lineage=lineage_repo,
        event_bus=bus,
        audit_service=audit_svc,
        metrics=metrics_registry,
    )
    upload_svc = DocumentUploadService(
        job_repository=repo,
        source_registry=registry,
        artifact_storage=storage,
        event_bus=bus,
        audit_service=audit_svc,
        metrics=metrics_registry,
        lifecycle=source_lifecycle,
    )
    parser_svc = DocumentParserService(artifact_storage=storage, source_registry=registry)
    # Fallback-only generator: не требует Ollama, всегда возвращает review_required.
    # Для тестов LLM-режима — отдельные респ-моки в test_run_pipeline.py.
    fallback = RAGCardFallbackGenerator()

    class _FallbackOnlyGenerator(RAGCardGenerator):
        def __init__(self) -> None:
            self._fallback = fallback

        def generate(self, section):  # type: ignore[override]
            return self._fallback.generate(section)

    card_registry = InMemoryRAGCardRegistry()
    metadata_validation = MetadataValidationService(registry=card_registry)

    # SETUP-06 (T-S06-023): full-wired RAGCardReviewService с per-test instances.
    from fe_bot.setup.card_review.decision_repository import (
        InMemoryReviewDecisionRepository,
    )
    from fe_bot.setup.card_review.edit_lock_repository import (
        InMemoryEditLockRepository,
    )
    from fe_bot.setup.card_review.log_repository import (
        InMemoryReviewLogRepository,
    )
    from fe_bot.setup.card_review.metrics import ReviewMetricsCollector
    from fe_bot.setup.card_review.readiness import ReviewReadinessCalculator
    from fe_bot.setup.card_review.version_repository import (
        InMemoryRAGCardVersionRepository,
    )

    review_decision_repo = InMemoryReviewDecisionRepository()
    review_log_repo = InMemoryReviewLogRepository()
    card_version_repo = InMemoryRAGCardVersionRepository()
    edit_lock_repo = InMemoryEditLockRepository()
    review_readiness = ReviewReadinessCalculator(card_registry=card_registry)
    review_metrics = ReviewMetricsCollector(metrics=metrics_registry)

    card_review = RAGCardReviewService(
        registry=card_registry,
        decision_repo=review_decision_repo,
        log_repo=review_log_repo,
        version_repo=card_version_repo,
        edit_lock_repo=edit_lock_repo,
        readiness_calculator=review_readiness,
        event_bus=bus,
        audit_service=audit_svc,
        metrics=review_metrics,
    )

    # S5 wiring: chunking + embedding + indexing. EmbeddingService использует
    # реальный LLMGateway, но в большинстве integration-тестов pipeline
    # не доходит до embedding (карточки в REVIEW_REQUIRED из-за low confidence
    # fallback-генератора). Тесты, проверяющие S5 явно, используют respx
    # для мокирования /api/embeddings.
    vector_index_client = InMemoryVectorIndexClient()
    chunking_svc = ChunkingService()
    embedding_svc = EmbeddingService(llm_gateway=LLMGateway(client=None))
    vector_indexer = VectorIndexerService(
        chunking=chunking_svc,
        embedding=embedding_svc,
        index_client=vector_index_client,
    )
    pipeline = SetupPipeline(
        orchestrator=orchestrator,
        parser=parser_svc,
        card_generator=_FallbackOnlyGenerator(),
        source_registry=registry,
        card_registry=card_registry,
        metadata_validation=metadata_validation,
        vector_indexer=vector_indexer,
    )

    # S6 wiring
    retrieval_svc = RetrievalService(embedding=embedding_svc, index_client=vector_index_client)
    evaluation_svc = RAGEvaluationService(retrieval=retrieval_svc)
    kb_repository = InMemoryKBRepository()
    kb_publish_svc = KBPublishService(repository=kb_repository)

    # S8 wiring (audit_log/audit_svc/metrics_registry уже созданы выше для
    # инъекции в DocumentUploadService — T-S02-011).
    idempotency_cache = InMemoryIdempotencyCache()
    batch_registry = InMemoryBatchRegistry()
    orphan_cleanup = OrphanCleanupService(storage=storage, registry=registry)
    # (SETUP-03 lifecycle создан выше — нужен для upload_svc.)
    # Подменяем metrics-registry в app.state — middleware читает оттуда.
    app.state.metrics = metrics_registry

    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_job_repository] = lambda: repo
    app.dependency_overrides[get_event_bus] = lambda: bus
    app.dependency_overrides[get_artifact_storage] = lambda: storage
    app.dependency_overrides[get_source_registry] = lambda: registry
    app.dependency_overrides[get_upload_service] = lambda: upload_svc
    app.dependency_overrides[get_parser_service] = lambda: parser_svc
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_card_registry] = lambda: card_registry
    app.dependency_overrides[get_metadata_validation] = lambda: metadata_validation
    app.dependency_overrides[get_card_review] = lambda: card_review
    app.dependency_overrides[get_vector_index_client] = lambda: vector_index_client
    app.dependency_overrides[get_vector_indexer] = lambda: vector_indexer
    app.dependency_overrides[get_retrieval_service] = lambda: retrieval_svc
    app.dependency_overrides[get_evaluation_service] = lambda: evaluation_svc
    app.dependency_overrides[get_kb_repository] = lambda: kb_repository
    app.dependency_overrides[get_kb_publish_service] = lambda: kb_publish_svc
    app.dependency_overrides[get_audit_log] = lambda: audit_log
    app.dependency_overrides[get_audit_service] = lambda: audit_svc
    app.dependency_overrides[get_metrics] = lambda: metrics_registry
    app.dependency_overrides[get_idempotency_cache] = lambda: idempotency_cache
    app.dependency_overrides[get_batch_registry] = lambda: batch_registry
    app.dependency_overrides[get_orphan_cleanup_service] = lambda: orphan_cleanup
    # SETUP-03 wiring.
    app.dependency_overrides[get_status_history_repo] = lambda: status_history_repo
    app.dependency_overrides[get_processing_log_repo] = lambda: processing_log_repo
    app.dependency_overrides[get_lineage_repo] = lambda: lineage_repo
    app.dependency_overrides[get_source_lifecycle] = lambda: source_lifecycle

    # SETUP-04: parser orchestrator wiring (T-S04-023..026).
    from schemas.setup.parse_job import ParserStrategy as _PSEnum

    from fe_bot.api.dependencies import (
        get_document_parser_orchestrator,
        get_parse_document_repo,
        get_parse_job_repo,
        get_parse_report_repo,
        get_parsed_section_repo,
        get_parser_registry,
    )
    from fe_bot.setup.parser.classifier import SectionClassifier as _Cls
    from fe_bot.setup.parser.document_repository import (
        InMemoryParseJobDocumentRepository as _PDR,
    )
    from fe_bot.setup.parser.job_repository import (
        InMemoryParseJobRepository as _PJR,
    )
    from fe_bot.setup.parser.orchestrator import (
        DocumentParserOrchestrator as _DPO,
    )
    from fe_bot.setup.parser.registry import ParserRegistry as _PR
    from fe_bot.setup.parser.report_repository import (
        InMemoryDocumentParseReportRepository as _PRR,
    )
    from fe_bot.setup.parser.section_repository import (
        InMemoryParsedSectionRepository as _PSR,
    )
    from fe_bot.setup.parser.strategies import (
        CSVParserStrategy as _CSV,
    )
    from fe_bot.setup.parser.strategies import (
        DOCXParserStrategy as _DOCX,
    )
    from fe_bot.setup.parser.strategies import (
        JSONParserStrategy as _JSON,
    )
    from fe_bot.setup.parser.strategies import (
        MarkdownParserStrategy as _MD,
    )
    from fe_bot.setup.parser.strategies import (
        PDFParserStrategy as _PDF,
    )
    from fe_bot.setup.parser.strategies import (
        PlainTextParserStrategy as _TXT,
    )
    from fe_bot.setup.parser.strategies import (
        XLSXParserStrategy as _XLSX,
    )

    parser_reg = _PR()
    parser_reg.register(_PSEnum.MARKDOWN, _MD())
    parser_reg.register(_PSEnum.TEXT, _TXT())
    parser_reg.register(_PSEnum.CSV, _CSV())
    parser_reg.register(_PSEnum.JSON, _JSON())
    parser_reg.register(_PSEnum.PDF_TEXT, _PDF())
    parser_reg.register(_PSEnum.DOCX, _DOCX())
    parser_reg.register(_PSEnum.XLSX, _XLSX())
    parse_job_repo = _PJR()
    parse_doc_repo = _PDR()
    parsed_section_repo = _PSR()
    parse_report_repo = _PRR()
    parser_orchestrator = _DPO(
        parse_job_repo=parse_job_repo,
        document_repo=parse_doc_repo,
        section_repo=parsed_section_repo,
        report_repo=parse_report_repo,
        parser_registry=parser_reg,
        classifier=_Cls(),
        source_lifecycle=source_lifecycle,
        artifact_storage=storage,
        event_bus=bus,
        audit_service=audit_svc,
        metrics=metrics_registry,
    )
    app.dependency_overrides[get_parser_registry] = lambda: parser_reg
    app.dependency_overrides[get_parse_job_repo] = lambda: parse_job_repo
    app.dependency_overrides[get_parse_document_repo] = lambda: parse_doc_repo
    app.dependency_overrides[get_parsed_section_repo] = lambda: parsed_section_repo
    app.dependency_overrides[get_parse_report_repo] = lambda: parse_report_repo
    app.dependency_overrides[get_document_parser_orchestrator] = lambda: parser_orchestrator

    # SETUP-05 RAG card generation wiring (T-S05-026..032).
    from fe_bot.api.dependencies import (
        get_card_generation_report_repo,
        get_ontology_mapper,
        get_prompt_template_registry,
        get_rag_card_job_repo,
        get_rag_card_orchestrator,
        get_rag_card_section_repo,
        get_rag_card_source_link_repo,
    )
    from fe_bot.api.setup.rag_cards_router import get_card_registry as _get_card_reg_router
    from fe_bot.setup.rag_card_generation.confidence_calculator import (
        ConfidenceCalculator as _ConfCalc05,
    )
    from fe_bot.setup.rag_card_generation.doc_id_generator import (
        DocIdGenerator as _DocId05,
    )
    from fe_bot.setup.rag_card_generation.doc_type_detector import (
        DocTypeDetector as _DocType05,
    )
    from fe_bot.setup.rag_card_generation.job_repository import (
        InMemoryRAGCardGenerationJobRepository as _RAGJob05,
    )
    from fe_bot.setup.rag_card_generation.job_section_repository import (
        InMemoryRAGCardGenerationJobSectionRepository as _RAGSec05,
    )
    from fe_bot.setup.rag_card_generation.llm_adapter import (
        FallbackGenerator as _Fallback05,
    )
    from fe_bot.setup.rag_card_generation.llm_adapter import (
        LLMCardAdapter as _LLMA05,
    )
    from fe_bot.setup.rag_card_generation.metadata_extractor import (
        MetadataExtractor as _MetaExt05,
    )
    from fe_bot.setup.rag_card_generation.ontology_mapper import (
        OntologyMapper as _Onto05,
    )
    from fe_bot.setup.rag_card_generation.orchestrator import (
        RAGCardGenerationOrchestrator as _RAGOrch05,
    )
    from fe_bot.setup.rag_card_generation.precheck import (
        CardValidationPrecheck as _Prech05,
    )
    from fe_bot.setup.rag_card_generation.precheck import (
        RAGCardDraft as _Draft05,
    )
    from fe_bot.setup.rag_card_generation.prompt_registry import (
        PromptTemplateRegistry as _PromptReg05,
    )
    from fe_bot.setup.rag_card_generation.report_repository import (
        InMemoryCardGenerationReportRepository as _CRR05,
    )
    from fe_bot.setup.rag_card_generation.source_link_repository import (
        InMemoryRAGCardSourceLinkRepository as _SL05,
    )

    class _IntegrationFallback(_Fallback05):
        """Deterministic fallback для integration-тестов (без Ollama)."""

        def generate_draft(self, prompt: str, *, doc_type: str) -> _Draft05:
            return _Draft05(
                doc_id="placeholder.x.v1",
                doc_type=doc_type,
                title="Section card",
                body_markdown="Generated section body for the RAG card. " * 3,
                front_matter={
                    "doc_id": "placeholder.x.v1",
                    "doc_type": doc_type,
                    "domain": ["naval"],
                    "phase": ["feature_synthesis"],
                },
                source_files=["src.md"],
                source_sections=["sec_001"],
                retrieval_tags=["sensor", "uptime"],
            )

    class _NoLLMGateway:
        def generate_structured(self, **_kwargs):  # type: ignore[no-untyped-def]
            from fe_bot.llm_gateway.exceptions import LLMUnavailableError

            raise LLMUnavailableError("integration tests use fallback only")

    rag_job_repo = _RAGJob05()
    rag_sec_repo = _RAGSec05()
    rag_link_repo = _SL05()
    rag_report_repo = _CRR05()
    rag_llm = _LLMA05(
        llm_gateway=_NoLLMGateway(),  # type: ignore[arg-type]
        fallback_generator=_IntegrationFallback(),
    )
    rag_orchestrator = _RAGOrch05(
        job_repo=rag_job_repo,
        job_section_repo=rag_sec_repo,
        card_registry=card_registry,
        source_link_repo=rag_link_repo,
        report_repo=rag_report_repo,
        parsed_section_repo=parsed_section_repo,
        ontology_mapper=_Onto05(),
        prompt_registry=_PromptReg05(),
        doc_type_detector=_DocType05(),
        metadata_extractor=_MetaExt05(),
        doc_id_generator=_DocId05(),
        llm_card_adapter=rag_llm,
        precheck=_Prech05(),
        confidence_calculator=_ConfCalc05(),
        source_lifecycle=source_lifecycle,
        artifact_storage=storage,
        event_bus=bus,
        audit_service=audit_svc,
        metrics=metrics_registry,
    )
    app.dependency_overrides[get_rag_card_orchestrator] = lambda: rag_orchestrator
    app.dependency_overrides[get_rag_card_job_repo] = lambda: rag_job_repo
    app.dependency_overrides[get_rag_card_section_repo] = lambda: rag_sec_repo
    app.dependency_overrides[get_rag_card_source_link_repo] = lambda: rag_link_repo
    app.dependency_overrides[get_card_generation_report_repo] = lambda: rag_report_repo
    app.dependency_overrides[get_ontology_mapper] = lambda: _Onto05()
    app.dependency_overrides[get_prompt_template_registry] = lambda: _PromptReg05()
    app.dependency_overrides[_get_card_reg_router] = lambda: card_registry
    yield app
    app.dependency_overrides.clear()
    # Очистка module-level singletons (на всякий случай для других тестов).
    _job_repository.clear()
    _event_bus.clear()
    _artifact_storage.clear()
    _source_registry.clear()
    _card_registry.clear()
    _ = _orchestrator  # keep import alive
    # LLMGateway не используется в этих тестах, но import нужен для type-hints
    _ = LLMGateway


@pytest.fixture
def client(app_with_clean_state: FastAPI) -> TestClient:
    return TestClient(app_with_clean_state)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Заголовки для обычного пользователя u1."""
    return {"X-User-Id": "u1", "X-Roles": "user"}


@pytest.fixture
def audit_log(app_with_clean_state: FastAPI) -> InMemoryAuditLog:
    """Доступ к audit log конкретного теста (T-S05-039)."""
    return app_with_clean_state.dependency_overrides[get_audit_log]()


@pytest.fixture
def metrics_registry(app_with_clean_state: FastAPI) -> MetricsRegistry:
    """Доступ к metrics registry конкретного теста (T-S05-039)."""
    return app_with_clean_state.dependency_overrides[get_metrics]()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-User-Id": "admin1", "X-Roles": "admin"}


@pytest.fixture
def expert_headers() -> dict[str, str]:
    """Domain expert — имеет kb.source.lineage.read и kb.source.log.read.

    User по спеку (§5.3) этих permissions не получает.
    """
    return {"X-User-Id": "expert1", "X-Roles": "domain_expert"}
