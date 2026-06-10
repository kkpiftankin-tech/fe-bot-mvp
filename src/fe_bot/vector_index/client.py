"""Vector Index Client (T-S01-031).

Контракт хранилища векторов. В MVP — in-memory; Qdrant-клиент подменится в
T-S01-INF-004 без изменения зависимых сервисов.

Идемпотентность: upsert по chunk_id заменяет существующую точку.
Coллекция выбирается по doc_type (см. INF-004).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

from schemas.rag.chunk import Chunk
from schemas.rag.embedding import Embedding


@dataclass(slots=True)
class VectorPoint:
    """Точка в векторной БД: id + вектор + payload (chunk-metadata)."""

    chunk_id: str
    doc_id: str
    doc_type: str
    chunk_type: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass(slots=True)
class SearchHit:
    """Результат поиска: chunk_id + score + payload."""

    chunk_id: str
    doc_id: str
    score: float
    payload: dict[str, Any]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity ∈ [-1, 1]. Возвращает 0 если любой из векторов нулевой."""
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class VectorIndexError(Exception):
    """Базовая ошибка vector index."""


class VectorIndexUnavailableError(VectorIndexError):
    """Qdrant недоступен (или эквивалент)."""


class VectorIndexClient(Protocol):
    """Контракт vector index — подменяется на QdrantClient в продакшене."""

    def upsert(self, *, collection: str, point: VectorPoint) -> None: ...

    def upsert_batch(self, *, collection: str, points: list[VectorPoint]) -> int:
        """Возвращает число успешно проиндексированных точек."""
        ...

    def count(self, collection: str) -> int: ...

    def list_collections(self) -> list[str]: ...

    def delete_collection(self, collection: str) -> None: ...

    def search(
        self,
        *,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...


class InMemoryVectorIndexClient:
    """In-memory реализация для MVP/тестов."""

    def __init__(self) -> None:
        # collection -> chunk_id -> VectorPoint
        self._store: dict[str, dict[str, VectorPoint]] = {}
        # При установке True — все методы выбрасывают VectorIndexUnavailableError
        # (полезно для resilience-тестов).
        self.unavailable: bool = False

    def upsert(self, *, collection: str, point: VectorPoint) -> None:
        self._check_available()
        self._store.setdefault(collection, {})[point.chunk_id] = point

    def upsert_batch(self, *, collection: str, points: list[VectorPoint]) -> int:
        self._check_available()
        self._store.setdefault(collection, {})
        for point in points:
            self._store[collection][point.chunk_id] = point
        return len(points)

    def count(self, collection: str) -> int:
        self._check_available()
        return len(self._store.get(collection, {}))

    def list_collections(self) -> list[str]:
        self._check_available()
        return sorted(self._store.keys())

    def delete_collection(self, collection: str) -> None:
        self._check_available()
        self._store.pop(collection, None)

    def search(
        self,
        *,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        """Cosine similarity ranking + optional payload-фильтры (точное равенство)."""
        self._check_available()
        points = self._store.get(collection, {}).values()
        hits: list[SearchHit] = []
        for point in points:
            if filters and not self._matches_filters(point.payload, filters):
                continue
            score = cosine_similarity(query_vector, point.vector)
            hits.append(
                SearchHit(
                    chunk_id=point.chunk_id,
                    doc_id=point.doc_id,
                    score=score,
                    payload=dict(point.payload),
                )
            )
        # Сортировка по score desc; tie-breaker по priority desc, затем chunk_id asc.
        hits.sort(
            key=lambda h: (
                -h.score,
                -h.payload.get("priority", 0),
                h.chunk_id,
            )
        )
        return hits[:top_k]

    @staticmethod
    def _matches_filters(payload: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            actual = payload.get(key)
            if isinstance(expected, list | tuple | set):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    def get(self, *, collection: str, chunk_id: str) -> VectorPoint | None:
        """Helper для тестов."""
        return self._store.get(collection, {}).get(chunk_id)

    def clear(self) -> None:
        """Helper для тестов."""
        self._store.clear()

    def _check_available(self) -> None:
        if self.unavailable:
            raise VectorIndexUnavailableError("Vector index marked as unavailable")


def collection_for_doc_type(doc_type: str) -> str:
    """Соглашение из INF-004: одна collection на doc_type."""
    return f"rag_{doc_type}"


def make_point(*, chunk: Chunk, embedding: Embedding, doc_type: str) -> VectorPoint:
    """Конструирует VectorPoint из Chunk + Embedding."""
    payload = {
        "doc_id": chunk.doc_id,
        "doc_type": doc_type,
        "chunk_type": chunk.chunk_type.value,
        "section_title": chunk.section_title,
        "priority": chunk.priority,
        "source_section_id": chunk.source_section_id,
        "chunk_text": chunk.chunk_text,
        **chunk.metadata,
    }
    return VectorPoint(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        doc_type=doc_type,
        chunk_type=chunk.chunk_type.value,
        vector=embedding.embedding_vector,
        payload=payload,
    )
