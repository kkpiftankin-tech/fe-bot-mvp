"""RAGCardSourceLinkRepository (SETUP-05 / T-S05-011).

Хранит lineage relations parsed_section ↔ rag_card.

Идемпотентен по ``(doc_id, card_version, source_section_id, relation_type)``:
повторный вызов ``link()`` возвращает существующую запись.

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.lineage import LineageRelationType
from schemas.setup.rag_card_source_link import RAGCardSourceLinkDTO


class RAGCardSourceLinkRepository(Protocol):
    def link(self, relation: RAGCardSourceLinkDTO) -> RAGCardSourceLinkDTO: ...

    def list_for_card(self, doc_id: str, card_version: str) -> list[RAGCardSourceLinkDTO]: ...

    def list_for_section(self, source_section_id: str) -> list[RAGCardSourceLinkDTO]: ...

    def list_for_document(self, source_document_id: str) -> list[RAGCardSourceLinkDTO]: ...


class InMemoryRAGCardSourceLinkRepository:
    """In-memory + thread-safe + idempotent."""

    def __init__(self) -> None:
        # source_link_id → DTO
        self._by_id: dict[str, RAGCardSourceLinkDTO] = {}
        # (doc_id, card_version, source_section_id, relation_type.value) → source_link_id
        self._by_unique_key: dict[tuple[str, str, str, str], str] = {}
        self._lock = threading.Lock()

    def link(self, relation: RAGCardSourceLinkDTO) -> RAGCardSourceLinkDTO:
        """Идемпотентное создание lineage relation.

        При повторном вызове с теми же ``(doc_id, card_version,
        source_section_id, relation_type)`` возвращается существующая запись —
        новая НЕ создаётся, source_link_id остаётся прежним.
        """
        key = (
            relation.doc_id,
            relation.card_version,
            relation.source_section_id,
            relation.relation_type.value,
        )
        with self._lock:
            existing_id = self._by_unique_key.get(key)
            if existing_id is not None:
                return self._by_id[existing_id]
            self._by_id[relation.source_link_id] = relation
            self._by_unique_key[key] = relation.source_link_id
            return relation

    def list_for_card(self, doc_id: str, card_version: str) -> list[RAGCardSourceLinkDTO]:
        with self._lock:
            return [
                r
                for r in self._by_id.values()
                if r.doc_id == doc_id and r.card_version == card_version
            ]

    def list_for_section(self, source_section_id: str) -> list[RAGCardSourceLinkDTO]:
        with self._lock:
            return [r for r in self._by_id.values() if r.source_section_id == source_section_id]

    def list_for_document(self, source_document_id: str) -> list[RAGCardSourceLinkDTO]:
        with self._lock:
            return [r for r in self._by_id.values() if r.source_document_id == source_document_id]

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_unique_key.clear()

    # ----- Snapshot persistence -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {lid: r.model_dump(mode="json") for lid, r in self._by_id.items()}

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_unique_key.clear()
            for lid, raw in data.items():
                relation = RAGCardSourceLinkDTO.model_validate(raw)
                self._by_id[lid] = relation
                self._by_unique_key[
                    (
                        relation.doc_id,
                        relation.card_version,
                        relation.source_section_id,
                        relation.relation_type.value
                        if isinstance(relation.relation_type, LineageRelationType)
                        else str(relation.relation_type),
                    )
                ] = lid
