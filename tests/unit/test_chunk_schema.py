"""Тесты Chunk и Embedding (T-S01-004, часть 1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.rag.chunk import Chunk, ChunkStatus, ChunkType
from schemas.rag.embedding import Embedding, EmbeddingStatus

pytestmark = pytest.mark.unit


def _make_chunk(**overrides: object) -> Chunk:
    defaults: dict[str, object] = {
        "chunk_id": "schema.tracks_fused.v1#formula#0",
        "doc_id": "schema.tracks_fused.v1",
        "chunk_type": ChunkType.FORMULA,
        "chunk_text": "closing_speed = range / dt",
        "embedding_text": "closing_speed formula for naval radar",
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Chunk.model_validate(defaults)


class TestChunk:
    def test_valid_chunk(self) -> None:
        ch = _make_chunk()
        assert ch.priority == 50
        assert ch.status == ChunkStatus.CREATED

    def test_all_10_chunk_types(self) -> None:
        assert {t.value for t in ChunkType} == {
            "summary",
            "definition",
            "inputs",
            "outputs",
            "formula",
            "validation",
            "examples",
            "agent_usage",
            "constraints",
            "metadata_summary",
        }

    def test_priority_range(self) -> None:
        with pytest.raises(ValidationError):
            _make_chunk(priority=-1)
        with pytest.raises(ValidationError):
            _make_chunk(priority=101)

    def test_empty_texts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_chunk(chunk_text="")
        with pytest.raises(ValidationError):
            _make_chunk(embedding_text="")

    def test_token_count_optional_but_non_negative(self) -> None:
        assert _make_chunk(token_count=None).token_count is None
        assert _make_chunk(token_count=0).token_count == 0
        with pytest.raises(ValidationError):
            _make_chunk(token_count=-1)


def _make_embedding(dimension: int = 4, **overrides: object) -> Embedding:
    defaults: dict[str, object] = {
        "embedding_id": "emb_001",
        "chunk_id": "chunk_001",
        "doc_id": "doc_001",
        "embedding_vector": [0.1] * dimension,
        "embedding_model": "nomic-embed-text",
        "dimension": dimension,
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Embedding.model_validate(defaults)


class TestEmbedding:
    def test_valid_embedding(self) -> None:
        emb = _make_embedding(dimension=768)
        assert emb.dimension == 768
        assert emb.status == EmbeddingStatus.CREATED

    def test_vector_dimension_must_match(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _make_embedding(dimension=4, embedding_vector=[0.1, 0.2, 0.3])
        assert "dimension" in str(exc.value)

    def test_dimension_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedding(dimension=0, embedding_vector=[])

    def test_empty_vector_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_embedding(dimension=0)
