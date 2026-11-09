"""Embedding Service (T-S01-030).

Batch-embedding chunks через LLM Gateway. По умолчанию использует
`nomic-embed-text` (см. schemas/common/defaults.DEFAULT_EMBEDDING_MODEL).

Стратегия отказоустойчивости:
- При LLMUnavailableError для одного chunk — retry до MAX_RETRIES_PER_CHUNK.
- Если retry исчерпаны — Embedding не создаётся, ошибка добавляется в
  EmbeddingBatchResult.errors. Pipeline в S5 решает, как это обработать
  (T-S01-033: failed embedding → весь pipeline → failed).

Логирует latency и количество ошибок (метрики DTO-26 / события).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from schemas.common.defaults import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
)
from schemas.rag.chunk import Chunk
from schemas.rag.embedding import Embedding, EmbeddingStatus

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)

MAX_RETRIES_PER_CHUNK = 2  # 1 initial + 2 retries = 3 попытки
RETRY_BACKOFF_SECONDS = (0.1, 0.3, 0.5)


@dataclass(slots=True)
class EmbeddingBatchResult:
    """Сводка прогона embedding-batch."""

    requested: int = 0
    succeeded: int = 0
    failed: int = 0
    embeddings: list[Embedding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    latency_ms_total: int = 0


class EmbeddingService:
    """Превращает Chunk в Embedding через LLM Gateway."""

    def __init__(
        self,
        *,
        llm_gateway: LLMGateway,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        index_version: str | None = None,
    ) -> None:
        self._gateway = llm_gateway
        self._model = model
        self._dimension = dimension
        self._index_version = index_version

    def embed_chunk(self, chunk: Chunk) -> Embedding | None:
        """Embed одиночный chunk. Возвращает None при исчерпании retry."""
        last_error: str | None = None
        for attempt in range(MAX_RETRIES_PER_CHUNK + 1):
            try:
                vector = self._gateway.generate_embedding(
                    text=chunk.embedding_text, model=self._model
                )
            except LLMUnavailableError as exc:
                last_error = f"unavailable: {exc}"
                logger.warning(
                    "Embedding LLM unavailable for chunk %s (attempt %d): %s",
                    chunk.chunk_id,
                    attempt + 1,
                    exc,
                )
                if attempt < MAX_RETRIES_PER_CHUNK:
                    time.sleep(RETRY_BACKOFF_SECONDS[attempt])
                continue
            except InvalidLLMOutputError as exc:
                last_error = f"invalid response: {exc}"
                logger.warning(
                    "Embedding invalid response for chunk %s: %s",
                    chunk.chunk_id,
                    exc,
                )
                break  # не retry — это контрактная ошибка
            else:
                if len(vector) != self._dimension:
                    last_error = (
                        f"dimension mismatch: got {len(vector)}, expected {self._dimension}"
                    )
                    logger.warning("Embedding dimension mismatch for chunk %s", chunk.chunk_id)
                    break
                return Embedding(
                    embedding_id=f"emb_{uuid.uuid4().hex[:12]}",
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    embedding_vector=vector,
                    embedding_model=self._model,
                    dimension=self._dimension,
                    index_version=self._index_version,
                    created_at=datetime.now(tz=UTC),
                    status=EmbeddingStatus.CREATED,
                    error_message=None,
                )

        # Все попытки исчерпаны.
        logger.error(
            "Failed to embed chunk %s after retries: %s",
            chunk.chunk_id,
            last_error,
        )
        return None

    def embed_batch(self, chunks: Sequence[Chunk]) -> EmbeddingBatchResult:
        """Прогоняет последовательно (Ollama не поддерживает true batch для embeddings)."""
        result = EmbeddingBatchResult(requested=len(chunks))
        start = time.monotonic()
        for chunk in chunks:
            embedding = self.embed_chunk(chunk)
            if embedding is None:
                result.failed += 1
                result.errors.append(f"EMBED[{chunk.chunk_id}]: retry exhausted")
            else:
                result.succeeded += 1
                result.embeddings.append(embedding)
        result.latency_ms_total = int((time.monotonic() - start) * 1000)
        return result
