"""RAG Card Registry.

Хранит RAGCard + RAGMetadata в рамках setup_job_id. В MVP — in-memory с
Protocol-интерфейсом; PostgreSQL-репозиторий подменится в S5+ без изменения
зависимых сервисов.

Гарантии:
- doc_id уникален в рамках одного setup_job.
- Update обновляет card.updated_at автоматически.
- Возвращаемые объекты — deep copy (изменения caller'а не затрагивают store).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata


@dataclass(slots=True)
class CardRecord:
    """Запись о карточке в реестре: карточка + metadata + setup_job_id."""

    setup_job_id: str
    card: RAGCard
    metadata: RAGMetadata
    section_id: str | None = None
    history: list[str] = field(default_factory=list)


class CardNotFoundError(LookupError):
    def __init__(self, doc_id: str) -> None:
        self.doc_id = doc_id
        super().__init__(f"RAG card not found: {doc_id}")


class CardAlreadyExistsError(ValueError):
    def __init__(self, doc_id: str) -> None:
        self.doc_id = doc_id
        super().__init__(f"RAG card already exists: {doc_id}")


class RAGCardRegistry(Protocol):
    """Контракт реестра RAG-карточек."""

    def add(
        self,
        *,
        setup_job_id: str,
        card: RAGCard,
        metadata: RAGMetadata,
        section_id: str | None = None,
    ) -> CardRecord: ...

    def get(self, doc_id: str) -> CardRecord: ...

    def exists(self, doc_id: str) -> bool: ...

    def list_for_job(
        self,
        setup_job_id: str,
        *,
        status_in: frozenset[CardStatus] | None = None,
    ) -> list[CardRecord]: ...

    def update(
        self,
        doc_id: str,
        *,
        card: RAGCard | None = None,
        metadata: RAGMetadata | None = None,
        note: str | None = None,
    ) -> CardRecord: ...

    def delete(self, doc_id: str) -> None: ...


class InMemoryRAGCardRegistry:
    """In-memory реализация для MVP."""

    def __init__(self) -> None:
        self._store: dict[str, CardRecord] = {}

    def add(
        self,
        *,
        setup_job_id: str,
        card: RAGCard,
        metadata: RAGMetadata,
        section_id: str | None = None,
    ) -> CardRecord:
        if card.doc_id in self._store:
            raise CardAlreadyExistsError(card.doc_id)
        if card.doc_id != metadata.doc_id:
            raise ValueError(
                f"Card.doc_id ({card.doc_id!r}) != Metadata.doc_id ({metadata.doc_id!r})"
            )
        record = CardRecord(
            setup_job_id=setup_job_id,
            card=card.model_copy(deep=True),
            metadata=metadata.model_copy(deep=True),
            section_id=section_id,
            history=[f"created: status={card.status.value}"],
        )
        self._store[card.doc_id] = record
        return self._clone(record)

    def get(self, doc_id: str) -> CardRecord:
        if doc_id not in self._store:
            raise CardNotFoundError(doc_id)
        return self._clone(self._store[doc_id])

    def exists(self, doc_id: str) -> bool:
        return doc_id in self._store

    def list_for_job(
        self,
        setup_job_id: str,
        *,
        status_in: frozenset[CardStatus] | None = None,
    ) -> list[CardRecord]:
        records = [
            r for r in self._store.values() if r.setup_job_id == setup_job_id
        ]
        if status_in is not None:
            records = [r for r in records if r.card.status in status_in]
        return [self._clone(r) for r in records]

    def update(
        self,
        doc_id: str,
        *,
        card: RAGCard | None = None,
        metadata: RAGMetadata | None = None,
        note: str | None = None,
    ) -> CardRecord:
        if doc_id not in self._store:
            raise CardNotFoundError(doc_id)
        existing = self._store[doc_id]
        new_card = card.model_copy(deep=True) if card is not None else existing.card
        # Обновляем updated_at если карточка действительно изменилась
        if card is not None:
            new_card = new_card.model_copy(
                update={"updated_at": datetime.now(tz=UTC)}
            )
        new_metadata = (
            metadata.model_copy(deep=True) if metadata is not None else existing.metadata
        )
        if new_card.doc_id != new_metadata.doc_id:
            raise ValueError(
                f"Card.doc_id ({new_card.doc_id!r}) != "
                f"Metadata.doc_id ({new_metadata.doc_id!r})"
            )

        updated = CardRecord(
            setup_job_id=existing.setup_job_id,
            card=new_card,
            metadata=new_metadata,
            section_id=existing.section_id,
            history=list(existing.history),
        )
        marker = f"status={new_card.status.value}"
        if note:
            updated.history.append(f"{marker}: {note}")
        else:
            updated.history.append(marker)
        self._store[doc_id] = updated
        return self._clone(updated)

    def delete(self, doc_id: str) -> None:
        if doc_id not in self._store:
            raise CardNotFoundError(doc_id)
        del self._store[doc_id]

    def clear(self) -> None:
        """Для тестов."""
        self._store.clear()

    @staticmethod
    def _clone(record: CardRecord) -> CardRecord:
        return CardRecord(
            setup_job_id=record.setup_job_id,
            card=record.card.model_copy(deep=True),
            metadata=record.metadata.model_copy(deep=True),
            section_id=record.section_id,
            history=list(record.history),
        )
