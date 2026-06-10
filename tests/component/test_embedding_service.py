"""Component-тесты Embedding Service (T-S01-030)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
import respx
from schemas.rag.chunk import Chunk, ChunkType

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.setup.embedding.service import (
    MAX_RETRIES_PER_CHUNK,
    EmbeddingBatchResult,
    EmbeddingService,
)

pytestmark = pytest.mark.component


def _make_chunk(chunk_id: str = "x.v1#summary#0") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id="x.v1",
        chunk_type=ChunkType.SUMMARY,
        chunk_text="sample chunk text",
        embedding_text="sample chunk text",
        priority=80,
        created_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )


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
    """Убирает реальный sleep между retry для скорости тестов."""
    with patch("fe_bot.setup.embedding.service.time.sleep"):
        yield


class TestEmbedChunk:
    @respx.mock
    def test_happy_path_returns_embedding(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response(768)
        )
        svc = EmbeddingService(llm_gateway=gateway)
        emb = svc.embed_chunk(_make_chunk())
        assert emb is not None
        assert emb.chunk_id == "x.v1#summary#0"
        assert emb.doc_id == "x.v1"
        assert len(emb.embedding_vector) == 768
        assert emb.dimension == 768
        assert emb.embedding_model == "nomic-embed-text"

    @respx.mock
    def test_dimension_mismatch_returns_none(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response(384)  # ожидается 768
        )
        svc = EmbeddingService(llm_gateway=gateway, dimension=768)
        emb = svc.embed_chunk(_make_chunk())
        assert emb is None

    @respx.mock
    def test_retry_on_unavailable(
        self, gateway: LLMGateway, no_sleep
    ) -> None:
        route = respx.post("http://localhost:11434/api/embeddings")
        route.side_effect = [
            httpx.ConnectError("down"),
            httpx.ConnectError("still down"),
            httpx.Response(200, json=_embed_response(768)),
        ]
        svc = EmbeddingService(llm_gateway=gateway)
        emb = svc.embed_chunk(_make_chunk())
        assert emb is not None  # succeeded on 3rd attempt

    @respx.mock
    def test_retries_exhausted_returns_none(
        self, gateway: LLMGateway, no_sleep
    ) -> None:
        respx.post("http://localhost:11434/api/embeddings").mock(
            side_effect=httpx.ConnectError("permanent down")
        )
        svc = EmbeddingService(llm_gateway=gateway)
        emb = svc.embed_chunk(_make_chunk())
        assert emb is None
        # Должно быть 1 + MAX_RETRIES_PER_CHUNK попыток.
        assert respx.calls.call_count == 1 + MAX_RETRIES_PER_CHUNK


class TestEmbedBatch:
    @respx.mock
    def test_batch_all_succeed(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response(768)
        )
        svc = EmbeddingService(llm_gateway=gateway)
        chunks = [_make_chunk(chunk_id=f"x.v1#summary#{i}") for i in range(4)]
        result = svc.embed_batch(chunks)
        assert isinstance(result, EmbeddingBatchResult)
        assert result.requested == 4
        assert result.succeeded == 4
        assert result.failed == 0
        assert len(result.embeddings) == 4
        assert result.errors == []
        assert result.latency_ms_total >= 0

    @respx.mock
    def test_batch_partial_failure(
        self, gateway: LLMGateway, no_sleep
    ) -> None:
        # Делаем mix: success / fail / success.
        route = respx.post("http://localhost:11434/api/embeddings")
        route.side_effect = [
            httpx.Response(200, json=_embed_response(768)),
            # Failed chunk: 3 попытки → все падают
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
            httpx.Response(200, json=_embed_response(768)),
        ]
        svc = EmbeddingService(llm_gateway=gateway)
        chunks = [_make_chunk(chunk_id=f"x.v1#summary#{i}") for i in range(3)]
        result = svc.embed_batch(chunks)
        assert result.succeeded == 2
        assert result.failed == 1
        assert len(result.errors) == 1
        assert "EMBED[x.v1#summary#1]" in result.errors[0]


class TestModelConfig:
    @respx.mock
    def test_custom_model_passed_to_gateway(self, gateway: LLMGateway) -> None:
        route = respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response(768)
        )
        svc = EmbeddingService(
            llm_gateway=gateway, model="custom-embed-model", dimension=768
        )
        svc.embed_chunk(_make_chunk())
        # Проверяем что в request пошёл правильный model.
        assert route.calls.call_count == 1
        request_body = route.calls.last.request.content.decode()
        assert "custom-embed-model" in request_body

    @respx.mock
    def test_index_version_attached_to_embedding(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json=_embed_response(768)
        )
        svc = EmbeddingService(
            llm_gateway=gateway, index_version="idx_2026_06_10_v1"
        )
        emb = svc.embed_chunk(_make_chunk())
        assert emb is not None
        assert emb.index_version == "idx_2026_06_10_v1"
