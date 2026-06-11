"""LineageRepository (SETUP-03 / T-S03-008).

Хранилище SourceLineageRelation с уникальностью по
(source_document_id, target_type, target_id, relation_type) — повторный
link не создаёт дубликат, возвращает существующую запись.

Дополнительно идемпотентность по event_id (двойная защита: и от retry'я
downstream-сервиса с тем же event_id, и от него же с новым event_id —
не создавая логический дубликат).

В продакшене (INF-002) — PostgreSQL с unique constraint + индексом по
(target_type, target_id) для reverse-lookup.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.lineage import (
    LineageCounters,
    LineageRelationType,
    LineageTargetType,
    SourceLineageRelation,
)

# Соответствие target_type → counter field в LineageCounters.
_COUNTER_FIELD: dict[LineageTargetType, str] = {
    LineageTargetType.PARSED_SECTION: "parsed_sections_count",
    LineageTargetType.RAG_CARD: "rag_cards_count",
    LineageTargetType.CHUNK: "chunks_count",
    LineageTargetType.EMBEDDING: "embeddings_count",
    LineageTargetType.PROCESSING_REPORT: "processing_reports_count",
    LineageTargetType.KNOWLEDGE_BASE_VERSION: "knowledge_base_versions_count",
}


class LineageRepository(Protocol):
    """Контракт хранилища lineage relations."""

    def link(self, relation: SourceLineageRelation) -> SourceLineageRelation:
        """Создаёт или возвращает существующую relation.

        Дедуп по двум ключам:
        - event_id (защита от retry с тем же event_id)
        - (source_document_id, target_type, target_id, relation_type)
          (защита от того же логического link через разные event_id)
        """
        ...

    def list_for_source(
        self,
        source_document_id: str,
        *,
        target_type: LineageTargetType | None = None,
    ) -> list[SourceLineageRelation]: ...

    def list_by_target(
        self, target_type: LineageTargetType, target_id: str
    ) -> list[SourceLineageRelation]:
        """Обратный поиск: какие source documents породили этот artifact."""
        ...

    def counters(self, source_document_id: str) -> LineageCounters: ...

    def get_by_event_id(
        self, event_id: str
    ) -> SourceLineageRelation | None: ...


class InMemoryLineageRepository:
    """In-memory реализация."""

    def __init__(self) -> None:
        # source_document_id -> list of relations
        self._by_source: dict[str, list[SourceLineageRelation]] = {}
        # (source_id, target_type, target_id, relation_type) -> relation
        self._by_unique_key: dict[
            tuple[str, str, str, str], SourceLineageRelation
        ] = {}
        # event_id -> relation
        self._by_event: dict[str, SourceLineageRelation] = {}
        # (target_type, target_id) -> list of relations (reverse lookup)
        self._by_target: dict[tuple[str, str], list[SourceLineageRelation]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _unique_key(
        rel: SourceLineageRelation,
    ) -> tuple[str, str, str, str]:
        return (
            rel.source_document_id,
            rel.target_type.value,
            rel.target_id,
            rel.relation_type.value,
        )

    def link(self, relation: SourceLineageRelation) -> SourceLineageRelation:
        with self._lock:
            # 1. Дедуп по event_id.
            existing_by_event = self._by_event.get(relation.event_id)
            if existing_by_event is not None:
                return existing_by_event.model_copy(deep=True)
            # 2. Дедуп по уникальному ключу (другой event_id, тот же link).
            unique = self._unique_key(relation)
            existing_by_key = self._by_unique_key.get(unique)
            if existing_by_key is not None:
                return existing_by_key.model_copy(deep=True)
            # 3. Новая relation.
            stored = relation.model_copy(deep=True)
            self._by_event[relation.event_id] = stored
            self._by_unique_key[unique] = stored
            self._by_source.setdefault(relation.source_document_id, []).append(stored)
            target_key = (relation.target_type.value, relation.target_id)
            self._by_target.setdefault(target_key, []).append(stored)
            return stored.model_copy(deep=True)

    def list_for_source(
        self,
        source_document_id: str,
        *,
        target_type: LineageTargetType | None = None,
    ) -> list[SourceLineageRelation]:
        with self._lock:
            relations = self._by_source.get(source_document_id, [])
            if target_type is not None:
                relations = [r for r in relations if r.target_type == target_type]
            return [r.model_copy(deep=True) for r in relations]

    def list_by_target(
        self, target_type: LineageTargetType, target_id: str
    ) -> list[SourceLineageRelation]:
        with self._lock:
            relations = self._by_target.get((target_type.value, target_id), [])
            return [r.model_copy(deep=True) for r in relations]

    def counters(self, source_document_id: str) -> LineageCounters:
        with self._lock:
            relations = self._by_source.get(source_document_id, [])
            counts: dict[str, int] = {}
            for rel in relations:
                field = _COUNTER_FIELD[rel.target_type]
                counts[field] = counts.get(field, 0) + 1
            return LineageCounters(**counts)

    def get_by_event_id(
        self, event_id: str
    ) -> SourceLineageRelation | None:
        with self._lock:
            rel = self._by_event.get(event_id)
            return rel.model_copy(deep=True) if rel else None

    def clear(self) -> None:
        with self._lock:
            self._by_source.clear()
            self._by_unique_key.clear()
            self._by_event.clear()
            self._by_target.clear()


# Re-export для удобства импорта в роутерах/сервисах.
__all__ = [
    "InMemoryLineageRepository",
    "LineageRelationType",
    "LineageRepository",
    "LineageTargetType",
]
