"""Integration: Vector Indexer Service (T-S01-031)."""

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
from schemas.rag.vector_index import VectorIndexStatus

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.setup.chunking.service import ChunkingService
from fe_bot.setup.embedding.service import EmbeddingService
from fe_bot.vector_index.client import (
    InMemoryVectorIndexClient,
    collection_for_doc_type,
)
from fe_bot.vector_index.service import VectorIndexerService

pytestmark = pytest.mark.integration


def _now() -> datetime:
    return datetime(2026, 6, 10, 10, 0, tzinfo=UTC)


def _make_pair(
    doc_id: str = "analytics_card.sensor.v1",
    *,
    doc_type: DocType = DocType.ANALYTICS_CARD,
) -> tuple[RAGCard, RAGMetadata]:
    card = RAGCard(
        doc_id=doc_id,
        doc_type=doc_type,
        title="Sensor analytics",
        version="1.0",
        status=CardStatus.APPROVED,
        body_markdown="# Sensor analytics\n\nfields and metrics",
        source_document_ids=["src_1"],
        created_by="generator",
        created_at=_now(),
        updated_at=_now(),
    )
    meta = RAGMetadata(
        doc_id=doc_id,
        doc_type=doc_type,
        phase=[Phase.FEATURE_SYNTHESIS],
        domain=[Domain.NAVAL],
        task_type=[TaskType.CLASSIFICATION],
        retrieval_tags=["sensor"],
        confidence_level=ConfidenceLevel.HIGH,
    )
    return card, meta


def _embed_response(dim: int = 768) -> dict:
    return {"embedding": [0.01] * dim}


@pytest.fixture
def gateway() -> LLMGateway:
    client = httpx.Client(base_url="http://localhost:11434", timeout=5.0)
    gw = LLMGateway(client=client, max_retries=0)
    yield gw
    gw.close()


@pytest.fixture
def no_sleep():
    with patch("fe_bot.setup.embedding.service.time.sleep"):
        yield


def _make_indexer(
    gateway: LLMGateway,
    index_client: InMemoryVectorIndexClient | None = None,
) -> VectorIndexerService:
    index_client = index_client or InMemoryVectorIndexClient()
    return VectorIndexerService(
        chunking=ChunkingService(),
        embedding=EmbeddingService(llm_gateway=gateway),
        index_client=index_client,
    )


class TestHappyPath:
    @respx.mock
    def test_indexes_single_card_to_correct_collection(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(json=_embed_response(768))
        client = InMemoryVectorIndexClient()
        svc = _make_indexer(gateway, client)
        card, meta = _make_pair()
        result = svc.index_cards([(card, meta)])

        # 3 chunk-а на карточку → 3 точки в одной collection.
        assert result.chunks_total == 3
        assert result.chunks_embedded == 3
        assert result.chunks_indexed == 3
        assert result.chunks_failed == 0
        assert result.vector_index is not None
        assert result.vector_index.status == VectorIndexStatus.READY

        collection = collection_for_doc_type(DocType.ANALYTICS_CARD.value)
        assert client.count(collection) == 3
        # Точки лежат с правильными chunk_id.
        assert (
            client.get(
                collection=collection,
                chunk_id="analytics_card.sensor.v1#summary#0",
            )
            is not None
        )

    @respx.mock
    def test_multiple_cards_routed_by_doc_type(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(json=_embed_response(768))
        client = InMemoryVectorIndexClient()
        svc = _make_indexer(gateway, client)
        pairs = [
            _make_pair(doc_id="analytics_card.a.v1", doc_type=DocType.ANALYTICS_CARD),
            _make_pair(doc_id="schema_card.b.v1", doc_type=DocType.SCHEMA_CARD),
        ]
        result = svc.index_cards(pairs)
        assert result.chunks_indexed == 6
        # 2 collections.
        cols = set(client.list_collections())
        assert collection_for_doc_type("analytics_card") in cols
        assert collection_for_doc_type("schema_card") in cols
        assert client.count(collection_for_doc_type("analytics_card")) == 3
        assert client.count(collection_for_doc_type("schema_card")) == 3

    @respx.mock
    def test_empty_input_returns_ready_index(self, gateway: LLMGateway) -> None:
        client = InMemoryVectorIndexClient()
        svc = _make_indexer(gateway, client)
        result = svc.index_cards([])
        assert result.chunks_total == 0
        assert result.vector_index is not None
        assert result.vector_index.status == VectorIndexStatus.READY

    @respx.mock
    def test_index_version_propagated_to_embeddings(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(json=_embed_response(768))
        svc = _make_indexer(gateway)
        card, meta = _make_pair()
        result = svc.index_cards([(card, meta)], index_version="idx_custom")
        assert result.index_version == "idx_custom"
        assert all(e.index_version == "idx_custom" for e in result.embeddings)


class TestIdempotency:
    @respx.mock
    def test_reindex_same_cards_replaces_points(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(json=_embed_response(768))
        client = InMemoryVectorIndexClient()
        svc = _make_indexer(gateway, client)
        card, meta = _make_pair()
        # Прогоняем дважды
        svc.index_cards([(card, meta)])
        svc.index_cards([(card, meta)])
        # Количество точек НЕ удвоилось (idempotent upsert по chunk_id).
        collection = collection_for_doc_type(DocType.ANALYTICS_CARD.value)
        assert client.count(collection) == 3
