"""Unit-тесты EmbeddingIndex (SETUP-12 / T-S12-013)."""

from __future__ import annotations

import math

import pytest

from fe_bot.taxonomy.embedding_index import (
    EmbeddingIndex,
    cosine_similarity,
)

pytestmark = pytest.mark.unit


class _CounterComputer:
    """Embedding-fake: возвращает фиксированный вектор + считает вызовы."""

    def __init__(self, vector: list[float] | None = None) -> None:
        self._vector = vector or [1.0, 0.0, 0.0]
        self.call_count = 0
        self.calls_for_text: dict[str, int] = {}

    def compute(self, text: str) -> list[float]:
        self.call_count += 1
        self.calls_for_text[text] = self.calls_for_text.get(text, 0) + 1
        return list(self._vector)


class TestCosineSimilarity:
    def test_identical(self) -> None:
        assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)

    def test_orthogonal(self) -> None:
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite(self) -> None:
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_empty_returns_zero(self) -> None:
        assert cosine_similarity([], [1.0]) == 0.0
        assert cosine_similarity([1.0], []) == 0.0

    def test_dimension_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="dimensions"):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_normalized_partial(self) -> None:
        # 45° between vectors
        v1 = [1.0, 0.0]
        v2 = [1.0, 1.0]
        sim = cosine_similarity(v1, v2)
        assert sim == pytest.approx(1.0 / math.sqrt(2.0))


class TestEmbeddingIndex:
    def test_first_call_invokes_computer(self) -> None:
        c = _CounterComputer([0.1, 0.2, 0.3])
        idx = EmbeddingIndex(c)
        out = idx.get_or_compute("hello")
        assert out == [0.1, 0.2, 0.3]
        assert c.call_count == 1

    def test_second_call_hits_cache(self) -> None:
        c = _CounterComputer()
        idx = EmbeddingIndex(c)
        idx.get_or_compute("hello")
        idx.get_or_compute("hello")
        assert c.call_count == 1

    def test_different_texts_recompute(self) -> None:
        c = _CounterComputer()
        idx = EmbeddingIndex(c)
        idx.get_or_compute("hello")
        idx.get_or_compute("world")
        assert c.call_count == 2

    def test_capacity_eviction(self) -> None:
        c = _CounterComputer()
        idx = EmbeddingIndex(c, capacity=2)
        idx.get_or_compute("a")
        idx.get_or_compute("b")
        idx.get_or_compute("c")  # evicts "a"
        # Re-fetch "a" → cache miss → recomputed
        idx.get_or_compute("a")
        assert c.calls_for_text["a"] == 2

    def test_stats(self) -> None:
        c = _CounterComputer()
        idx = EmbeddingIndex(c)
        idx.get_or_compute("x")
        idx.get_or_compute("x")
        idx.get_or_compute("y")
        stats = idx.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["size"] == 2

    def test_returns_copy_not_internal(self) -> None:
        c = _CounterComputer([1.0, 2.0, 3.0])
        idx = EmbeddingIndex(c)
        out = idx.get_or_compute("x")
        out.append(99.0)  # пытаемся мутировать
        out2 = idx.get_or_compute("x")
        # Cache не должен быть затронут
        assert out2 == [1.0, 2.0, 3.0]

    def test_clear(self) -> None:
        c = _CounterComputer()
        idx = EmbeddingIndex(c)
        idx.get_or_compute("x")
        idx.clear()
        idx.get_or_compute("x")
        assert c.calls_for_text["x"] == 2

    def test_invalid_capacity(self) -> None:
        c = _CounterComputer()
        with pytest.raises(ValueError):
            EmbeddingIndex(c, capacity=0)
