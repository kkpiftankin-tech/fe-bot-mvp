"""Retrieval Service (T-S01-035).

Поиск по индексированной базе знаний:
1. Эмбеддит query через EmbeddingService.
2. Делегирует поиск по collection(-ям) в VectorIndexClient.
3. Возвращает top-K hits с дедупликацией по doc_id (опционально).

В Runtime-стадии RetrievalAgent использует этот сервис; в Setup — он же
используется для retrieval-tests (T-S01-036/037).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from schemas.rag.chunk import Chunk, ChunkType

from fe_bot.setup.embedding.service import EmbeddingService
from fe_bot.vector_index.client import (
    SearchHit,
    VectorIndexClient,
    collection_for_doc_type,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievalRequest:
    """Параметры одного retrieval-запроса."""

    query: str
    top_k: int = 5
    doc_types: list[str] | None = None  # None = искать во всех collections
    filters: dict[str, Any] | None = None
    deduplicate_by_doc: bool = True
    min_score: float | None = None
    # SETUP-12 wiring: иерархический фильтр через TaxonomyFilter.
    # Простые critеria попадают в pre-filter (filters dict); сложные
    # (bitmap, path_prefix) применяются post-фильтром через
    # apply_filter_to_hits. См. retrieval.py.
    taxonomy_filter: Any | None = None


@dataclass(slots=True)
class RetrievalResult:
    """Результат retrieval по одному запросу."""

    query: str
    top_k: int
    hits: list[SearchHit] = field(default_factory=list)
    collections_searched: list[str] = field(default_factory=list)
    latency_ms: int = 0
    error_message: str | None = None

    @property
    def doc_ids(self) -> list[str]:
        """Уникальные doc_id в порядке появления."""
        seen: set[str] = set()
        out: list[str] = []
        for hit in self.hits:
            if hit.doc_id not in seen:
                seen.add(hit.doc_id)
                out.append(hit.doc_id)
        return out

    @property
    def is_empty(self) -> bool:
        return not self.hits


class RetrievalService:
    """Объединяет embedding + vector search."""

    def __init__(
        self,
        *,
        embedding: EmbeddingService,
        index_client: VectorIndexClient,
        default_top_k: int = 5,
    ) -> None:
        self._embedding = embedding
        self._index_client = index_client
        self._default_top_k = default_top_k

    def search(self, request: RetrievalRequest) -> RetrievalResult:
        start = datetime.now(tz=UTC)
        result = RetrievalResult(query=request.query, top_k=request.top_k)

        # 1. Embed query через временный Chunk-эмулятор.
        query_chunk = Chunk(
            chunk_id="__query__",
            doc_id="__query__",
            chunk_type=ChunkType.SUMMARY,
            chunk_text=request.query,
            embedding_text=request.query.lower().strip(),
            priority=100,
            created_at=start,
            token_count=None,
        )
        query_embedding = self._embedding.embed_chunk(query_chunk)
        if query_embedding is None:
            result.error_message = "Failed to embed query (LLM unavailable or invalid)"
            return result
        query_vector = query_embedding.embedding_vector

        # 2. Определяем collection(s).
        collections: list[str] = []
        if request.doc_types:
            collections = [collection_for_doc_type(dt) for dt in request.doc_types]
        else:
            collections = self._index_client.list_collections()

        # 3. SETUP-12 wiring: merge taxonomy_filter exact-match критериев
        # с пользовательскими filters (taxonomy pre-фильтр).
        effective_filters = dict(request.filters or {})
        if request.taxonomy_filter is not None:
            try:
                effective_filters.update(
                    request.taxonomy_filter.to_payload_dict()
                )
            except AttributeError:
                logger.warning(
                    "RetrievalRequest.taxonomy_filter has no to_payload_dict; "
                    "ignored: %r",
                    request.taxonomy_filter,
                )

        # 4. Search в каждой collection.
        all_hits: list[SearchHit] = []
        for collection in collections:
            try:
                hits = self._index_client.search(
                    collection=collection,
                    query_vector=query_vector,
                    top_k=request.top_k,
                    filters=effective_filters or None,
                )
            except Exception as exc:
                logger.warning("Search in collection %s failed: %s", collection, exc)
                continue
            all_hits.extend(hits)

        result.collections_searched = collections

        # 5. SETUP-12 wiring: taxonomy post-фильтр для критериев, не
        # выразимых через exact-match (path_prefix, bitmap-tests).
        if (
            request.taxonomy_filter is not None
            and getattr(request.taxonomy_filter, "has_bitwise_criteria", False)
        ):
            try:
                from fe_bot.taxonomy import apply_filter_to_hits

                all_hits = apply_filter_to_hits(
                    all_hits, request.taxonomy_filter
                )
            except Exception:
                logger.exception(
                    "Failed to apply taxonomy post-filter; returning unfiltered hits"
                )

        # 6. Глобальное ранжирование + опциональный фильтр по min_score + дедуп.
        if request.min_score is not None:
            all_hits = [h for h in all_hits if h.score >= request.min_score]
        # Сортируем глобально (если искали в нескольких collections).
        all_hits.sort(key=lambda h: -h.score)

        if request.deduplicate_by_doc:
            seen_docs: set[str] = set()
            unique: list[SearchHit] = []
            for hit in all_hits:
                if hit.doc_id in seen_docs:
                    continue
                seen_docs.add(hit.doc_id)
                unique.append(hit)
                if len(unique) >= request.top_k:
                    break
            result.hits = unique
        else:
            result.hits = all_hits[: request.top_k]

        result.latency_ms = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)
        return result

    def search_batch(self, requests: Iterable[RetrievalRequest]) -> list[RetrievalResult]:
        return [self.search(r) for r in requests]
