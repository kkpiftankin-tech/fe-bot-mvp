"""Integration: resilience pipeline (T-S01-033).

Эмулирует сбои Ollama (embeddings) и Qdrant (vector index) и проверяет, что:
- pipeline корректно переводит job в FAILED;
- артефакты предыдущих шагов (карточки в registry) НЕ удаляются.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
import respx
from schemas.rag.ontology import (
    ConfidenceLevel,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata
from schemas.setup.rag_setup_job import RAGSetupJob, SetupJobStatus

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.setup.card_registry.service import (
    CardRecord,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.chunking.service import ChunkingService
from fe_bot.setup.embedding.service import EmbeddingService
from fe_bot.setup.events import EventBus
from fe_bot.setup.metadata_validation.service import MetadataValidationService
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.pipeline import SetupPipeline
from fe_bot.setup.repository import InMemoryJobRepository
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.vector_index.client import InMemoryVectorIndexClient
from fe_bot.vector_index.service import VectorIndexerService

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime(2026, 6, 10, 10, 0, tzinfo=UTC)


def _make_high_confidence_pair(doc_id: str) -> tuple[RAGCard, RAGMetadata]:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        title=f"Card {doc_id}",
        version="1.0",
        status=CardStatus.METADATA_VALIDATED,
        body_markdown=f"# {doc_id}\n\nfull body content",
        source_document_ids=["src_1"],
        created_by="generator",
        created_at=_now(),
        updated_at=_now(),
    )
    meta = RAGMetadata(
        doc_id=doc_id,
        doc_type=DocType.ANALYTICS_CARD,
        phase=[Phase.FEATURE_SYNTHESIS],
        domain=[Domain.NAVAL],
        task_type=[TaskType.CLASSIFICATION],
        retrieval_tags=["tag"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


@pytest.fixture
def services():
    """Создаёт минимальный pipeline-сетап с уже подготовленными high-confidence карточками."""
    repo = InMemoryJobRepository()
    bus = EventBus()
    orchestrator = SetupOrchestrator(repo, bus)
    source_registry = InMemorySourceRegistry()
    card_registry = InMemoryRAGCardRegistry()

    # Создаём job в нужном статусе и добавляем 1 source document, чтобы пройти precondition.
    job = orchestrator.create_job(user_id="u1", project_name="Resilience test")
    sid = job.setup_job_id

    # Заранее регистрируем карточку в metadata_validated — pipeline должен
    # её auto-approve и отправить в indexing.
    card, meta = _make_high_confidence_pair(f"analytics_card.r1.{sid[-6:]}.v1")
    card_registry.add(setup_job_id=sid, card=card, metadata=meta)

    return (
        sid,
        repo,
        bus,
        orchestrator,
        source_registry,
        card_registry,
    )


def _make_pipeline(
    *,
    orchestrator,
    source_registry,
    card_registry,
    gateway: LLMGateway,
    index_client: InMemoryVectorIndexClient,
) -> SetupPipeline:
    # Embedding/chunking/vector
    chunking = ChunkingService()
    embedding = EmbeddingService(llm_gateway=gateway)
    indexer = VectorIndexerService(
        chunking=chunking,
        embedding=embedding,
        index_client=index_client,
    )
    # Создаём фиктивный parser и card_generator — pipeline не дойдёт до них
    # потому что мы прокидываем job уже в files_uploaded.
    metadata_validation = MetadataValidationService(registry=card_registry)
    return SetupPipeline(
        orchestrator=orchestrator,
        parser=None,  # type: ignore[arg-type]
        card_generator=None,  # type: ignore[arg-type]
        source_registry=source_registry,
        card_registry=card_registry,
        metadata_validation=metadata_validation,
        vector_indexer=indexer,
    )


def _move_job_to_indexing(
    repo: InMemoryJobRepository,
    sid: str,
) -> RAGSetupJob:
    """Переводит job из DRAFT прямо в METADATA_VALIDATING для теста S5."""
    job = repo.get(sid)
    path = [
        SetupJobStatus.FILES_UPLOADED,
        SetupJobStatus.PARSING,
        SetupJobStatus.SECTIONS_EXTRACTED,
        SetupJobStatus.RAG_CARDS_GENERATING,
        SetupJobStatus.METADATA_VALIDATING,
    ]
    for status in path:
        job.transition_to(status)
        job.current_step = status.value
    repo.save(job)
    return job


@pytest.fixture
def no_sleep():
    with patch("fe_bot.setup.embedding.service.time.sleep"):
        yield


class TestOllamaEmbeddingsDown:
    """T-S01-033: Ollama down во время embedding → pipeline FAILED."""

    @respx.mock
    def test_embeddings_503_marks_job_failed(self, services, no_sleep) -> None:
        sid, repo, _bus, orchestrator, source_registry, card_registry = services
        respx.post("http://localhost:11434/api/embeddings").respond(status_code=503)

        client = httpx.Client(base_url="http://localhost:11434", timeout=5.0)
        gateway = LLMGateway(client=client, max_retries=0)
        index_client = InMemoryVectorIndexClient()
        pipeline = _make_pipeline(
            orchestrator=orchestrator,
            source_registry=source_registry,
            card_registry=card_registry,
            gateway=gateway,
            index_client=index_client,
        )

        # Подготавливаем job через прямую установку статуса.
        _move_job_to_indexing(repo, sid)

        # Запускаем S5-часть напрямую через _run_indexing_pipeline.
        from fe_bot.setup.pipeline import PipelineResult

        r = PipelineResult(
            setup_job_id=sid,
            final_status=SetupJobStatus.METADATA_VALIDATING,
            documents_total=0,
            documents_parsed=0,
            documents_failed=0,
            sections_extracted=0,
            cards_generated=0,
            cards_review_required=0,
            cards_used_fallback=0,
        )
        # auto-approve metadata_validated карточек
        pipeline._auto_approve_validated_cards(sid)  # noqa: SLF001
        pipeline._run_indexing_pipeline(sid, r)  # noqa: SLF001

        gateway.close()

        # Job → FAILED
        job = repo.get(sid)
        assert job.status == SetupJobStatus.FAILED
        # Карточки НЕ удалены из registry (сохранены для retry).
        assert card_registry.list_for_job(sid), "Cards must be preserved on failure"


class TestVectorDBDown:
    """T-S01-033: Qdrant недоступен → pipeline FAILED, artifacts preserved."""

    @respx.mock
    def test_vector_db_unavailable_marks_job_failed(self, services) -> None:
        sid, repo, _bus, orchestrator, source_registry, card_registry = services
        respx.post("http://localhost:11434/api/embeddings").respond(
            json={"embedding": [0.01] * 768}
        )
        client = httpx.Client(base_url="http://localhost:11434", timeout=5.0)
        gateway = LLMGateway(client=client, max_retries=0)
        index_client = InMemoryVectorIndexClient()
        index_client.unavailable = True  # Симулируем Qdrant down

        pipeline = _make_pipeline(
            orchestrator=orchestrator,
            source_registry=source_registry,
            card_registry=card_registry,
            gateway=gateway,
            index_client=index_client,
        )
        _move_job_to_indexing(repo, sid)

        from fe_bot.setup.pipeline import PipelineResult

        r = PipelineResult(
            setup_job_id=sid,
            final_status=SetupJobStatus.METADATA_VALIDATING,
            documents_total=0,
            documents_parsed=0,
            documents_failed=0,
            sections_extracted=0,
            cards_generated=0,
            cards_review_required=0,
            cards_used_fallback=0,
        )
        pipeline._auto_approve_validated_cards(sid)  # noqa: SLF001
        pipeline._run_indexing_pipeline(sid, r)  # noqa: SLF001

        gateway.close()

        # Job → FAILED из-за VECTOR_DB_UNAVAILABLE.
        job = repo.get(sid)
        assert job.status == SetupJobStatus.FAILED
        # Карточки сохранены.
        records: list[CardRecord] = card_registry.list_for_job(sid)
        assert records
        # vector_index в результате — статус FAILED.
        assert r.vector_index is not None
        assert r.vector_index.status.value == "failed"
        # В errors есть VECTOR_DB_UNAVAILABLE сообщение.
        assert any("VECTOR_DB_UNAVAILABLE" in e for e in r.errors)


class TestPartialEmbeddingFailure:
    """Часть chunks упала → vector_index ready с failed_chunks_count > 0."""

    @respx.mock
    def test_some_chunks_fail_partial_index(self, services, no_sleep) -> None:
        sid, repo, _bus, orchestrator, source_registry, card_registry = services
        # 3 chunks → 1 успех, 1 фейл, 1 успех (для одной карточки).
        route = respx.post("http://localhost:11434/api/embeddings")
        route.side_effect = [
            httpx.Response(200, json={"embedding": [0.01] * 768}),
            # fail chunk
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.Response(200, json={"embedding": [0.01] * 768}),
        ]
        client = httpx.Client(base_url="http://localhost:11434", timeout=5.0)
        gateway = LLMGateway(client=client, max_retries=0)
        index_client = InMemoryVectorIndexClient()
        pipeline = _make_pipeline(
            orchestrator=orchestrator,
            source_registry=source_registry,
            card_registry=card_registry,
            gateway=gateway,
            index_client=index_client,
        )
        _move_job_to_indexing(repo, sid)

        from fe_bot.setup.pipeline import PipelineResult

        r = PipelineResult(
            setup_job_id=sid,
            final_status=SetupJobStatus.METADATA_VALIDATING,
            documents_total=0,
            documents_parsed=0,
            documents_failed=0,
            sections_extracted=0,
            cards_generated=0,
            cards_review_required=0,
            cards_used_fallback=0,
        )
        pipeline._auto_approve_validated_cards(sid)  # noqa: SLF001
        pipeline._run_indexing_pipeline(sid, r)  # noqa: SLF001

        gateway.close()

        # 2 успех / 1 fail
        assert r.chunks_total == 3
        assert r.chunks_indexed == 2
        assert r.chunks_failed == 1
        assert r.vector_index is not None
        # Частичный успех = READY (есть хотя бы один indexed)
        assert r.vector_index.status.value == "ready"
        # И errors[] содержит EMBED сообщение.
        assert any("EMBED[" in e for e in r.errors)
