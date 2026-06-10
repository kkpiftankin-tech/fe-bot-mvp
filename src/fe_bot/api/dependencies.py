"""FastAPI dependencies: auth, orchestrator, repository.

В тестах перекрываются через `app.dependency_overrides`.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status

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
from fe_bot.setup.parser.service import DocumentParserService
from fe_bot.setup.pipeline import SetupPipeline
from fe_bot.setup.publish.service import (
    InMemoryKBRepository,
    KBPublishService,
)
from fe_bot.setup.repository import InMemoryJobRepository
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
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
_upload_service = DocumentUploadService(
    job_repository=_job_repository,
    source_registry=_source_registry,
    artifact_storage=_artifact_storage,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_metrics,
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
_orphan_cleanup = OrphanCleanupService(
    storage=_artifact_storage, registry=_source_registry
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
