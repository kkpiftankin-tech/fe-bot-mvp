"""Chunking Service (T-S01-029).

Стратегия (MVP): на каждую approved-карточку производится 3 chunk-а:
- `summary`        — заголовок + первые ~500 символов body.
- `definition`     — полный body (обрезается до CHUNK_CHAR_BUDGET).
- `metadata_summary` — текстовое представление metadata для retrieval по фильтрам.

chunk_id детерминирован: `{doc_id}#{chunk_type}#{n}`. Повторный chunking той
же карточки даёт идентичные chunk_id (INV-ID-003).

embedding_text — это короткая retrieval-оптимизированная версия chunk_text:
lowercased, схлопнутые пробелы. Длина ограничена CHUNK_CHAR_BUDGET.

Source: docs/06-rag/chunk-schema.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime

from schemas.rag.chunk import Chunk, ChunkStatus, ChunkType
from schemas.rag.rag_card import RAGCard
from schemas.rag.rag_metadata import RAGMetadata

# Максимум символов в chunk_text/embedding_text. ~1024 токенов ≈ 4000 символов
# для llama3.2 / nomic-embed-text (BPE rate ≈ 0.25 token/char).
CHUNK_CHAR_BUDGET = 4000
SUMMARY_CHAR_BUDGET = 600

# Приоритет по умолчанию (0..100) — выше = важнее при rerank.
_CHUNK_PRIORITY: dict[ChunkType, int] = {
    ChunkType.SUMMARY: 80,
    ChunkType.DEFINITION: 70,
    ChunkType.METADATA_SUMMARY: 40,
}


_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_for_embedding(text: str) -> str:
    """Lowercased, схлопнутые пробелы, обрезано по бюджету."""
    normalized = _WHITESPACE_RE.sub(" ", text.lower()).strip()
    return normalized[:CHUNK_CHAR_BUDGET]


def _summarize(body: str) -> str:
    body = body.strip()
    if len(body) <= SUMMARY_CHAR_BUDGET:
        return body
    return body[:SUMMARY_CHAR_BUDGET].rstrip() + "…"


def _metadata_to_text(card: RAGCard, metadata: RAGMetadata) -> str:
    """Конструирует поисковую сводку metadata."""
    parts = [
        f"Title: {card.title}",
        f"Doc type: {card.doc_type.value}",
        f"Domain: {', '.join(d.value for d in metadata.domain) or '-'}",
        f"Phases: {', '.join(p.value for p in metadata.phase) or '-'}",
        f"Tags: {', '.join(metadata.retrieval_tags) or '-'}",
    ]
    if metadata.task_type:
        parts.append(f"Tasks: {', '.join(t.value for t in metadata.task_type)}")
    if metadata.data_source:
        parts.append(f"Sources: {', '.join(s.value for s in metadata.data_source)}")
    if metadata.agent_targets:
        parts.append(f"Agents: {', '.join(metadata.agent_targets)}")
    return "\n".join(parts)


class ChunkingService:
    """Превращает (RAGCard, RAGMetadata) в список Chunk-ов."""

    def chunk_card(self, *, card: RAGCard, metadata: RAGMetadata) -> list[Chunk]:
        if card.doc_id != metadata.doc_id:
            raise ValueError(
                f"Card.doc_id ({card.doc_id!r}) != Metadata.doc_id ({metadata.doc_id!r})"
            )
        now = datetime.now(tz=UTC)
        section_title = card.title
        source_section = card.source_section_ids[0] if card.source_section_ids else None

        chunks: list[Chunk] = []

        # 1. summary
        summary_body = _summarize(card.body_markdown)
        chunks.append(
            Chunk(
                chunk_id=self._make_id(card.doc_id, ChunkType.SUMMARY, 0),
                doc_id=card.doc_id,
                chunk_type=ChunkType.SUMMARY,
                section_title=section_title,
                chunk_text=summary_body,
                embedding_text=_normalize_for_embedding(summary_body),
                metadata={
                    "doc_type": card.doc_type.value,
                    "version": card.version,
                    "card_status": card.status.value,
                },
                priority=_CHUNK_PRIORITY[ChunkType.SUMMARY],
                source_section_id=source_section,
                token_count=None,
                created_at=now,
                status=ChunkStatus.CREATED,
            )
        )

        # 2. definition (полный body, ограниченный по бюджету)
        definition_body = card.body_markdown.strip()
        if len(definition_body) > CHUNK_CHAR_BUDGET:
            definition_body = definition_body[:CHUNK_CHAR_BUDGET].rstrip() + "…"
        chunks.append(
            Chunk(
                chunk_id=self._make_id(card.doc_id, ChunkType.DEFINITION, 0),
                doc_id=card.doc_id,
                chunk_type=ChunkType.DEFINITION,
                section_title=section_title,
                chunk_text=definition_body,
                embedding_text=_normalize_for_embedding(definition_body),
                metadata={
                    "doc_type": card.doc_type.value,
                    "version": card.version,
                },
                priority=_CHUNK_PRIORITY[ChunkType.DEFINITION],
                source_section_id=source_section,
                token_count=None,
                created_at=now,
                status=ChunkStatus.CREATED,
            )
        )

        # 3. metadata_summary
        meta_text = _metadata_to_text(card, metadata)
        chunks.append(
            Chunk(
                chunk_id=self._make_id(card.doc_id, ChunkType.METADATA_SUMMARY, 0),
                doc_id=card.doc_id,
                chunk_type=ChunkType.METADATA_SUMMARY,
                section_title=section_title,
                chunk_text=meta_text,
                embedding_text=_normalize_for_embedding(meta_text),
                metadata={
                    "doc_type": card.doc_type.value,
                    "version": card.version,
                    "facet_only": True,
                },
                priority=_CHUNK_PRIORITY[ChunkType.METADATA_SUMMARY],
                source_section_id=source_section,
                token_count=None,
                created_at=now,
                status=ChunkStatus.CREATED,
            )
        )

        return chunks

    def chunk_many(self, pairs: Iterable[tuple[RAGCard, RAGMetadata]]) -> list[Chunk]:
        out: list[Chunk] = []
        for card, metadata in pairs:
            out.extend(self.chunk_card(card=card, metadata=metadata))
        return out

    @staticmethod
    def _make_id(doc_id: str, chunk_type: ChunkType, n: int) -> str:
        return f"{doc_id}#{chunk_type.value}#{n}"
