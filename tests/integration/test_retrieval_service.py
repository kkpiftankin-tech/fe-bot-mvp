"""Integration: Retrieval Service (T-S01-035)."""

from __future__ import annotations

import httpx
import pytest
import respx

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.retrieval.service import RetrievalRequest, RetrievalService
from fe_bot.setup.embedding.service import EmbeddingService
from fe_bot.vector_index.client import (
    InMemoryVectorIndexClient,
    VectorPoint,
    collection_for_doc_type,
)

pytestmark = pytest.mark.integration


def _seed_index(client: InMemoryVectorIndexClient) -> None:
    """Кладём 3 разных карточки в индекс."""
    collection_a = collection_for_doc_type("analytics_card")
    collection_s = collection_for_doc_type("schema_card")
    # Точка с вектором [1,0,0,…] — близка к query [1,0,0,…]
    client.upsert(
        collection=collection_a,
        point=VectorPoint(
            chunk_id="a1#summary#0",
            doc_id="a1",
            doc_type="analytics_card",
            chunk_type="summary",
            vector=[1.0] + [0.0] * 767,
            payload={"doc_id": "a1", "title": "Match A", "priority": 80},
        ),
    )
    client.upsert(
        collection=collection_a,
        point=VectorPoint(
            chunk_id="a2#summary#0",
            doc_id="a2",
            doc_type="analytics_card",
            chunk_type="summary",
            vector=[0.0, 1.0] + [0.0] * 766,  # ортогональный query
            payload={"doc_id": "a2", "title": "Orthogonal", "priority": 50},
        ),
    )
    client.upsert(
        collection=collection_s,
        point=VectorPoint(
            chunk_id="s1#summary#0",
            doc_id="s1",
            doc_type="schema_card",
            chunk_type="summary",
            vector=[0.7, 0.7] + [0.0] * 766,  # средняя похожесть
            payload={"doc_id": "s1", "title": "Schema partial match", "priority": 60},
        ),
    )


@pytest.fixture
def gateway() -> LLMGateway:
    client = httpx.Client(base_url="http://localhost:11434", timeout=5.0)
    gw = LLMGateway(client=client, max_retries=0)
    yield gw
    gw.close()


@pytest.fixture
def retrieval_service(gateway: LLMGateway) -> RetrievalService:
    embedding = EmbeddingService(llm_gateway=gateway)
    index = InMemoryVectorIndexClient()
    _seed_index(index)
    return RetrievalService(embedding=embedding, index_client=index)


def _embed_response(vector: list[float]) -> dict:
    return {"embedding": vector}


class TestSearch:
    @respx.mock
    def test_top_k_respected(self, retrieval_service: RetrievalService) -> None:
        # Query vector совпадает с a1, ортогонален a2.
        query_vec = [1.0] + [0.0] * 767
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response(query_vec)
        )
        result = retrieval_service.search(RetrievalRequest(query="A1 match", top_k=2))
        assert len(result.hits) == 2
        assert result.hits[0].doc_id == "a1"  # самый похожий
        # a2 (orthogonal) имеет score=0, не должен быть first.
        assert result.hits[0].score > result.hits[1].score
        assert result.latency_ms >= 0

    @respx.mock
    def test_search_across_multiple_collections(
        self, retrieval_service: RetrievalService
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response([1.0] + [0.0] * 767)
        )
        result = retrieval_service.search(
            RetrievalRequest(query="anything", top_k=5)
        )
        searched = set(result.collections_searched)
        assert collection_for_doc_type("analytics_card") in searched
        assert collection_for_doc_type("schema_card") in searched

    @respx.mock
    def test_filter_by_doc_types(
        self, retrieval_service: RetrievalService
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response([1.0] + [0.0] * 767)
        )
        result = retrieval_service.search(
            RetrievalRequest(query="x", top_k=10, doc_types=["analytics_card"])
        )
        # Только analytics_card collection.
        assert result.collections_searched == [
            collection_for_doc_type("analytics_card")
        ]
        # s1 не должен быть в результатах.
        assert all(h.doc_id != "s1" for h in result.hits)

    @respx.mock
    def test_deduplication_by_doc_id(
        self, gateway: LLMGateway
    ) -> None:
        embedding = EmbeddingService(llm_gateway=gateway)
        index = InMemoryVectorIndexClient()
        # 3 chunks на одну doc.
        for i in range(3):
            index.upsert(
                collection=collection_for_doc_type("analytics_card"),
                point=VectorPoint(
                    chunk_id=f"d1#summary#{i}",
                    doc_id="d1",
                    doc_type="analytics_card",
                    chunk_type="summary",
                    vector=[1.0] + [0.0] * 767,
                    payload={"doc_id": "d1", "title": "T"},
                ),
            )
        svc = RetrievalService(embedding=embedding, index_client=index)
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response([1.0] + [0.0] * 767)
        )
        result = svc.search(RetrievalRequest(query="x", top_k=5))
        # Из-за dedup только 1 hit (все 3 chunks на одну doc).
        assert len(result.hits) == 1

    @respx.mock
    def test_min_score_filter(
        self, retrieval_service: RetrievalService
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response([1.0] + [0.0] * 767)
        )
        result = retrieval_service.search(
            RetrievalRequest(query="x", top_k=5, min_score=0.5)
        )
        # a2 (orthogonal, score=0) отфильтрован.
        assert all(h.score >= 0.5 for h in result.hits)
        assert not any(h.doc_id == "a2" for h in result.hits)

    @respx.mock
    def test_no_context_when_index_empty(self, gateway: LLMGateway) -> None:
        embedding = EmbeddingService(llm_gateway=gateway)
        empty_index = InMemoryVectorIndexClient()
        svc = RetrievalService(embedding=embedding, index_client=empty_index)
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response([1.0] + [0.0] * 767)
        )
        result = svc.search(RetrievalRequest(query="x", top_k=5))
        assert result.is_empty
        assert result.doc_ids == []

    @respx.mock
    def test_embed_failure_returns_error(
        self, retrieval_service: RetrievalService
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").mock(
            side_effect=httpx.ConnectError("down")
        )
        # Без sleep для скорости
        from unittest.mock import patch
        with patch("fe_bot.setup.embedding.service.time.sleep"):
            result = retrieval_service.search(RetrievalRequest(query="x", top_k=5))
        assert result.is_empty
        assert result.error_message is not None
        assert "embed" in result.error_message.lower()
