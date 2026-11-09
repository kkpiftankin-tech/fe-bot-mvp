"""Vector Indexer Service (T-S01-031, продолжение).

Объединяет ChunkingService + EmbeddingService + VectorIndexClient в один
сервис, который для набора (RAGCard, RAGMetadata) производит upsert в Qdrant
и возвращает VectorIndexDTO.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from schemas.rag.embedding import Embedding
from schemas.rag.rag_card import RAGCard
from schemas.rag.rag_metadata import RAGMetadata
from schemas.rag.vector_index import VectorIndex, VectorIndexStatus

from fe_bot.setup.chunking.service import ChunkingService
from fe_bot.setup.embedding.service import EmbeddingService
from fe_bot.vector_index.client import (
    VectorIndexClient,
    VectorIndexError,
    VectorIndexUnavailableError,
    VectorPoint,
    collection_for_doc_type,
    make_point,
)

logger = logging.getLogger(__name__)


# SETUP-12 wiring: ключи payload'а из front_matter, которые попадают
# в VectorIndex для retrieval-фильтров. См. ADR-HTC-07.
_TAXONOMY_PAYLOAD_KEYS = frozenset(
    {
        "taxonomy_version_id",
        "taxonomy_node_id",
        "taxonomy_path",
        "classification_bitmap",
        "primary_l0",
        "primary_l1",
        "primary_l2",
        "unknown_at_level",
    }
)


def _extract_taxonomy_payload(
    front_matter: dict[str, object] | None,
) -> dict[str, object]:
    """Возвращает подмножество front_matter с таксономическими ключами.

    Пустой dict если ни одного ключа не найдено (rule_based mode).
    """
    if not front_matter:
        return {}
    return {
        k: v for k, v in front_matter.items() if k in _TAXONOMY_PAYLOAD_KEYS
    }


@dataclass(slots=True)
class IndexingResult:
    """Сводка индексации для UI / processing report."""

    index_version: str
    chunks_total: int = 0
    chunks_embedded: int = 0
    chunks_indexed: int = 0
    chunks_failed: int = 0
    embeddings: list[Embedding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    vector_index: VectorIndex | None = None


class VectorIndexerService:
    """Прогоняет chunking → embedding → upsert для набора карточек."""

    def __init__(
        self,
        *,
        chunking: ChunkingService,
        embedding: EmbeddingService,
        index_client: VectorIndexClient,
    ) -> None:
        self._chunking = chunking
        self._embedding = embedding
        self._index_client = index_client

    def index_cards(
        self,
        pairs: Iterable[tuple[RAGCard, RAGMetadata]],
        *,
        index_version: str | None = None,
    ) -> IndexingResult:
        version = index_version or self._make_index_version()
        result = IndexingResult(index_version=version)

        cards_pairs = list(pairs)
        if not cards_pairs:
            result.vector_index = self._make_index_record(
                version=version,
                chunks_total=0,
                indexed=0,
                failed=0,
                status=VectorIndexStatus.READY,
                collections=[],
            )
            return result

        # Step 1: chunking
        all_chunks = []
        chunk_to_doc_type: dict[str, str] = {}
        # SETUP-12 wiring: taxonomy payload per card (taken из
        # metadata.front_matter, который заполняется RAG-card orchestrator'ом
        # в llm-mode). Backward-compat: пусто в rule_based mode.
        chunk_to_taxonomy_payload: dict[str, dict[str, object]] = {}
        for card, metadata in cards_pairs:
            chunks = self._chunking.chunk_card(card=card, metadata=metadata)
            # SETUP-12: front_matter живёт на самой RAGCard (orchestrator
            # копирует туда taxonomy_* поля), а не на структурированной
            # RAGMetadata. См. orchestrator step 12.
            tax_payload = _extract_taxonomy_payload(card.front_matter)
            all_chunks.extend(chunks)
            for chunk in chunks:
                chunk_to_doc_type[chunk.chunk_id] = card.doc_type.value
                if tax_payload:
                    chunk_to_taxonomy_payload[chunk.chunk_id] = tax_payload
        result.chunks_total = len(all_chunks)

        if not all_chunks:
            result.vector_index = self._make_index_record(
                version=version,
                chunks_total=0,
                indexed=0,
                failed=0,
                status=VectorIndexStatus.READY,
                collections=[],
            )
            return result

        # Step 2: embedding (batch)
        # Прокидываем index_version в эмбеддинги через временную подмену
        # приватного атрибута (упрощение: EmbeddingService хранит
        # index_version в __init__, тут переопределяем на время прогона).
        original_iv = self._embedding._index_version
        try:
            self._embedding._index_version = version
            embed_batch = self._embedding.embed_batch(all_chunks)
        finally:
            self._embedding._index_version = original_iv

        result.chunks_embedded = embed_batch.succeeded
        result.embeddings = embed_batch.embeddings
        result.errors.extend(embed_batch.errors)
        # Карта chunk_id → embedding для тех, что прошли.
        emb_by_chunk = {e.chunk_id: e for e in embed_batch.embeddings}

        # Step 3: indexing (upsert по collection)
        points_by_collection: dict[str, list[VectorPoint]] = {}
        chunks_by_id = {c.chunk_id: c for c in all_chunks}
        for chunk_id, embedding in emb_by_chunk.items():
            chunk = chunks_by_id[chunk_id]
            doc_type = chunk_to_doc_type[chunk_id]
            collection = collection_for_doc_type(doc_type)
            point = make_point(
                chunk=chunk,
                embedding=embedding,
                doc_type=doc_type,
                extra_payload=chunk_to_taxonomy_payload.get(chunk_id),
            )
            points_by_collection.setdefault(collection, []).append(point)

        collections_touched: list[str] = []
        try:
            for collection, points in points_by_collection.items():
                upserted = self._index_client.upsert_batch(collection=collection, points=points)
                result.chunks_indexed += upserted
                collections_touched.append(collection)
        except VectorIndexUnavailableError as exc:
            result.errors.append(f"VECTOR_DB_UNAVAILABLE: {exc}")
            logger.error("Vector DB unavailable during indexing: %s", exc)
            result.vector_index = self._make_index_record(
                version=version,
                chunks_total=result.chunks_total,
                indexed=result.chunks_indexed,
                failed=result.chunks_total - result.chunks_indexed,
                status=VectorIndexStatus.FAILED,
                collections=collections_touched,
            )
            return result
        except VectorIndexError as exc:
            result.errors.append(f"INDEXING_FAILED: {exc}")
            logger.error("Vector indexing failed: %s", exc)
            result.vector_index = self._make_index_record(
                version=version,
                chunks_total=result.chunks_total,
                indexed=result.chunks_indexed,
                failed=result.chunks_total - result.chunks_indexed,
                status=VectorIndexStatus.FAILED,
                collections=collections_touched,
            )
            return result

        result.chunks_failed = result.chunks_total - result.chunks_indexed

        status = (
            VectorIndexStatus.READY
            if result.chunks_indexed > 0 and result.chunks_failed == 0
            else (
                VectorIndexStatus.FAILED
                if result.chunks_indexed == 0
                else VectorIndexStatus.READY  # частичный успех — всё равно READY
            )
        )
        result.vector_index = self._make_index_record(
            version=version,
            chunks_total=result.chunks_total,
            indexed=result.chunks_indexed,
            failed=result.chunks_failed,
            status=status,
            collections=collections_touched,
        )
        return result

    @staticmethod
    def _make_index_version() -> str:
        now = datetime.now(tz=UTC)
        return f"idx_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    def _make_index_record(
        self,
        *,
        version: str,
        chunks_total: int,
        indexed: int,
        failed: int,
        status: VectorIndexStatus,
        collections: list[str],
    ) -> VectorIndex:
        return VectorIndex(
            index_version=version,
            knowledge_base_version=None,
            collection_names=collections,
            embedding_model=self._embedding._model,
            chunks_count=chunks_total,
            indexed_chunks_count=indexed,
            failed_chunks_count=failed,
            status=status,
            created_at=datetime.now(tz=UTC),
            metadata={},
        )
