"""FastAPI dependencies: auth, orchestrator, repository.

В тестах перекрываются через `app.dependency_overrides`.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from schemas.setup.parse_job import ParserStrategy as ParserStrategyEnum

from fe_bot.audit.service import AuditService, InMemoryAuditLog
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import (
    AuthService,
    ForbiddenError,
    Principal,
    UnauthenticatedError,
)
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
from fe_bot.setup.parser.classifier import SectionClassifier
from fe_bot.setup.parser.document_repository import (
    InMemoryParseJobDocumentRepository,
)
from fe_bot.setup.parser.job_repository import InMemoryParseJobRepository
from fe_bot.setup.parser.orchestrator import DocumentParserOrchestrator
from fe_bot.setup.parser.registry import ParserRegistry
from fe_bot.setup.parser.report_repository import (
    InMemoryDocumentParseReportRepository,
)
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.parser.service import DocumentParserService
from fe_bot.setup.parser.strategies import (
    CSVParserStrategy,
    DOCXParserStrategy,
    JSONParserStrategy,
    MarkdownParserStrategy,
    PDFParserStrategy,
    PlainTextParserStrategy,
    XLSXParserStrategy,
)
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

# Module-level singletons. Production replaces with proper DI container.
_auth_service = AuthService()
_job_repository = InMemoryJobRepository()
_event_bus = EventBus()
_orchestrator = SetupOrchestrator(_job_repository, _event_bus)
_artifact_storage = InMemoryArtifactStorage()
_source_registry = InMemorySourceRegistry()
_audit_log = InMemoryAuditLog()
_audit_service = AuditService(_audit_log)
_metrics = MetricsRegistry()

# SETUP-03: Source Registry repositories + lifecycle service.
# Создаём до _upload_service — он использует lifecycle для T-S03-019.
_status_history_repo = InMemoryStatusHistoryRepository()
_processing_log_repo = InMemoryProcessingLogRepository()
_lineage_repo = InMemoryLineageRepository()
_source_lifecycle = SourceLifecycleService(
    registry=_source_registry,
    status_history=_status_history_repo,
    processing_log=_processing_log_repo,
    lineage=_lineage_repo,
    event_bus=_event_bus,  # T-S03-020: source.document.* events
    audit_service=_audit_service,  # T-S03-022
    metrics=_metrics,
)

_upload_service = DocumentUploadService(
    job_repository=_job_repository,
    source_registry=_source_registry,
    artifact_storage=_artifact_storage,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_metrics,
    lifecycle=_source_lifecycle,
)
_parser_service = DocumentParserService(
    artifact_storage=_artifact_storage,
    source_registry=_source_registry,
)
_llm_gateway = LLMGateway()
_card_generator = RAGCardGenerator(
    llm_gateway=_llm_gateway,
    fallback_generator=RAGCardFallbackGenerator(),
)
_card_registry = InMemoryRAGCardRegistry()
_metadata_validation = MetadataValidationService(registry=_card_registry)
_card_review = RAGCardReviewService(registry=_card_registry)
_vector_index_client = InMemoryVectorIndexClient()
_chunking = ChunkingService()
_embedding_service = EmbeddingService(llm_gateway=_llm_gateway)
_vector_indexer = VectorIndexerService(
    chunking=_chunking,
    embedding=_embedding_service,
    index_client=_vector_index_client,
)
_pipeline = SetupPipeline(
    orchestrator=_orchestrator,
    parser=_parser_service,
    card_generator=_card_generator,
    source_registry=_source_registry,
    card_registry=_card_registry,
    metadata_validation=_metadata_validation,
    vector_indexer=_vector_indexer,
)
_retrieval_service = RetrievalService(
    embedding=_embedding_service,
    index_client=_vector_index_client,
)
_evaluation_service = RAGEvaluationService(retrieval=_retrieval_service)
_kb_repository = InMemoryKBRepository()
_kb_publish = KBPublishService(repository=_kb_repository)
# _audit_log / _audit_service / _metrics — определены раньше (нужны для DocumentUploadService).
_idempotency_cache = InMemoryIdempotencyCache()
_batch_registry = InMemoryBatchRegistry()
_orphan_cleanup = OrphanCleanupService(storage=_artifact_storage, registry=_source_registry)

# SETUP-04: parser orchestrator singletons.
_parser_registry = ParserRegistry()
_parser_registry.register(ParserStrategyEnum.MARKDOWN, MarkdownParserStrategy())
_parser_registry.register(ParserStrategyEnum.TEXT, PlainTextParserStrategy())
_parser_registry.register(ParserStrategyEnum.CSV, CSVParserStrategy())
_parser_registry.register(ParserStrategyEnum.JSON, JSONParserStrategy())
_parser_registry.register(ParserStrategyEnum.PDF_TEXT, PDFParserStrategy())
_parser_registry.register(ParserStrategyEnum.DOCX, DOCXParserStrategy())
_parser_registry.register(ParserStrategyEnum.XLSX, XLSXParserStrategy())

_parse_job_repo = InMemoryParseJobRepository()
_parse_doc_repo = InMemoryParseJobDocumentRepository()
_parsed_section_repo = InMemoryParsedSectionRepository()
_parse_report_repo = InMemoryDocumentParseReportRepository()
_section_classifier = SectionClassifier()

_document_parser_orchestrator = DocumentParserOrchestrator(
    parse_job_repo=_parse_job_repo,
    document_repo=_parse_doc_repo,
    section_repo=_parsed_section_repo,
    report_repo=_parse_report_repo,
    parser_registry=_parser_registry,
    classifier=_section_classifier,
    source_lifecycle=_source_lifecycle,
    artifact_storage=_artifact_storage,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_metrics,
)


def get_auth_service() -> AuthService:
    return _auth_service


def get_orchestrator() -> SetupOrchestrator:
    return _orchestrator


def get_event_bus() -> EventBus:
    return _event_bus


def get_job_repository() -> InMemoryJobRepository:
    return _job_repository


def get_artifact_storage() -> InMemoryArtifactStorage:
    return _artifact_storage


def get_source_registry() -> InMemorySourceRegistry:
    return _source_registry


def get_upload_service() -> DocumentUploadService:
    return _upload_service


def get_parser_service() -> DocumentParserService:
    return _parser_service


def get_pipeline() -> SetupPipeline:
    return _pipeline


def get_card_registry() -> InMemoryRAGCardRegistry:
    return _card_registry


def get_metadata_validation() -> MetadataValidationService:
    return _metadata_validation


def get_card_review() -> RAGCardReviewService:
    return _card_review


def get_vector_index_client() -> InMemoryVectorIndexClient:
    return _vector_index_client


def get_vector_indexer() -> VectorIndexerService:
    return _vector_indexer


def get_retrieval_service() -> RetrievalService:
    return _retrieval_service


def get_evaluation_service() -> RAGEvaluationService:
    return _evaluation_service


def get_kb_repository() -> InMemoryKBRepository:
    return _kb_repository


def get_kb_publish_service() -> KBPublishService:
    return _kb_publish


def get_audit_log() -> InMemoryAuditLog:
    return _audit_log


def get_audit_service() -> AuditService:
    return _audit_service


def get_metrics() -> MetricsRegistry:
    return _metrics


def get_idempotency_cache() -> InMemoryIdempotencyCache:
    return _idempotency_cache


def get_batch_registry() -> InMemoryBatchRegistry:
    return _batch_registry


def get_orphan_cleanup_service() -> OrphanCleanupService:
    return _orphan_cleanup


# SETUP-03 DI factories.


def get_status_history_repo() -> InMemoryStatusHistoryRepository:
    return _status_history_repo


def get_processing_log_repo() -> InMemoryProcessingLogRepository:
    return _processing_log_repo


def get_lineage_repo() -> InMemoryLineageRepository:
    return _lineage_repo


def get_source_lifecycle() -> SourceLifecycleService:
    return _source_lifecycle


# SETUP-04 DI factories.


def get_parser_registry() -> ParserRegistry:
    return _parser_registry


def get_parse_job_repo() -> InMemoryParseJobRepository:
    return _parse_job_repo


def get_parse_document_repo() -> InMemoryParseJobDocumentRepository:
    return _parse_doc_repo


def get_parsed_section_repo() -> InMemoryParsedSectionRepository:
    return _parsed_section_repo


def get_parse_report_repo() -> InMemoryDocumentParseReportRepository:
    return _parse_report_repo


def get_document_parser_orchestrator() -> DocumentParserOrchestrator:
    return _document_parser_orchestrator


def get_principal(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_roles: str | None = Header(default=None, alias="X-Roles"),
) -> Principal:
    """Извлекает Principal из HTTP-заголовков. В MVP — простой stub."""
    try:
        return get_auth_service().authenticate(x_user_id, x_roles)
    except UnauthenticatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def require_permission(
    permission: Permission,
) -> Callable[[Principal], Principal]:
    """Builder для зависимости, требующей конкретный permission."""

    def dependency(
        principal: Principal = Depends(get_principal),
    ) -> Principal:
        try:
            get_auth_service().require(principal, permission)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return principal

    return dependency
