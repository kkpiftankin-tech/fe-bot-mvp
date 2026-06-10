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
    get_card_registry,
    get_card_review,
    get_evaluation_service,
    get_event_bus,
    get_idempotency_cache,
    get_job_repository,
    get_kb_publish_service,
    get_kb_repository,
    get_metadata_validation,
    get_metrics,
    get_orchestrator,
    get_parser_service,
    get_pipeline,
    get_retrieval_service,
    get_source_registry,
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
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
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
    upload_svc = DocumentUploadService(
        job_repository=repo,
        source_registry=registry,
        artifact_storage=storage,
        event_bus=bus,
    )
    parser_svc = DocumentParserService(
        artifact_storage=storage, source_registry=registry
    )
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
    card_review = RAGCardReviewService(registry=card_registry)

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
    retrieval_svc = RetrievalService(
        embedding=embedding_svc, index_client=vector_index_client
    )
    evaluation_svc = RAGEvaluationService(retrieval=retrieval_svc)
    kb_repository = InMemoryKBRepository()
    kb_publish_svc = KBPublishService(repository=kb_repository)

    # S8 wiring
    audit_log = InMemoryAuditLog()
    audit_svc = AuditService(audit_log)
    metrics_registry = MetricsRegistry()
    idempotency_cache = InMemoryIdempotencyCache()
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
def admin_headers() -> dict[str, str]:
    return {"X-User-Id": "admin1", "X-Roles": "admin"}
