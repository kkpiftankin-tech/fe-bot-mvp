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

from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata
from schemas.setup.rag_card_metadata import RAGCardMetadataDTO


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
    """In-memory реализация для MVP.

    SETUP-05 extension: дополнительно поддерживается версионирование карточек
    через ``save_version``/``get_version``/``list_versions`` с уникальностью
    ``(doc_id, card_version)``, хранение typed front matter через
    ``save_metadata``/``get_metadata`` и attachment markdown artifact через
    ``attach_artifact``.

    Legacy API (``add``/``get``/``list_for_job``) сохранён без изменений и
    продолжает работать с RAGMetadata.
    """

    def __init__(self) -> None:
        self._store: dict[str, CardRecord] = {}
        # SETUP-05 (T-S05-010) version-aware storage.
        # _versions: (doc_id, card_version) → RAGCard
        self._versions: dict[tuple[str, str], RAGCard] = {}
        # _version_order: doc_id → ordered list of card_versions (insertion order).
        self._version_order: dict[str, list[str]] = {}
        # _metadata_v05: (doc_id, card_version) → RAGCardMetadataDTO
        self._metadata_v05: dict[tuple[str, str], RAGCardMetadataDTO] = {}
        # _artifacts: (doc_id, card_version) → list of (artifact_id, artifact_type).
        self._artifacts: dict[tuple[str, str], list[tuple[str, str]]] = {}

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
        if doc_id in self._store:
            return self._clone(self._store[doc_id])
        # SETUP-05+ fallback: посмотреть в _versions (latest версия).
        versions = self._version_order.get(doc_id)
        if versions:
            card = self._versions[(doc_id, versions[-1])]
            from schemas.rag.ontology import Domain, Phase
            from schemas.rag.rag_metadata import RAGMetadata

            try:
                meta = RAGMetadata.model_validate(card.front_matter)
            except Exception:  # noqa: BLE001
                meta = RAGMetadata(
                    doc_id=card.doc_id,
                    doc_type=card.doc_type,
                    phase=[Phase.FEATURE_SYNTHESIS],
                    domain=[Domain.NAVAL],
                    retrieval_tags=list(card.front_matter.get("retrieval_tags", []))
                    or ["unknown"],
                )
            return CardRecord(
                setup_job_id=card.setup_job_id or "",
                card=card,
                metadata=meta,
                section_id=card.primary_source_section_id,
            )
        raise CardNotFoundError(doc_id)

    def exists(self, doc_id: str) -> bool:
        if doc_id in self._store:
            return True
        return bool(self._version_order.get(doc_id))

    def list_for_job(
        self,
        setup_job_id: str,
        *,
        status_in: frozenset[CardStatus] | None = None,
    ) -> list[CardRecord]:
        records = [r for r in self._store.values() if r.setup_job_id == setup_job_id]

        # SETUP-05+ unification: cards stored via save_version() в _versions —
        # latest версия каждой карточки выставляется как CardRecord (используя
        # metadata из card.front_matter, поскольку RAGMetadata отдельно не
        # хранится для SETUP-05 cards).
        seen_doc_ids = {r.card.doc_id for r in records}
        for doc_id, versions in self._version_order.items():
            if doc_id in seen_doc_ids or not versions:
                continue
            card = self._versions[(doc_id, versions[-1])]
            if card.setup_job_id != setup_job_id:
                continue
            # Synthesize metadata from card.front_matter for legacy CardRecord shape.
            from schemas.rag.rag_metadata import RAGMetadata

            try:
                meta = RAGMetadata.model_validate(card.front_matter)
            except Exception:  # noqa: BLE001
                # Minimal valid metadata fallback с required-полями из ontology.
                from schemas.rag.ontology import Domain, Phase

                meta = RAGMetadata(
                    doc_id=card.doc_id,
                    doc_type=card.doc_type,
                    phase=[Phase.FEATURE_SYNTHESIS],
                    domain=[Domain.NAVAL],
                    retrieval_tags=list(card.front_matter.get("retrieval_tags", []))
                    or ["unknown"],
                )
            records.append(
                CardRecord(
                    setup_job_id=setup_job_id,
                    card=card,
                    metadata=meta,
                    section_id=card.primary_source_section_id,
                )
            )
            seen_doc_ids.add(doc_id)

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
        # SETUP-05+: если карточка только в _versions — материализуем её в
        # _store (через get) для legacy update flow.
        if doc_id not in self._store:
            try:
                synthesized = self.get(doc_id)
            except CardNotFoundError:
                raise
            # add к _store
            self._store[doc_id] = CardRecord(
                setup_job_id=synthesized.setup_job_id,
                card=synthesized.card,
                metadata=synthesized.metadata,
                section_id=synthesized.section_id,
            )
        existing = self._store[doc_id]
        new_card = card.model_copy(deep=True) if card is not None else existing.card
        # Обновляем updated_at если карточка действительно изменилась
        if card is not None:
            new_card = new_card.model_copy(update={"updated_at": datetime.now(tz=UTC)})
        new_metadata = metadata.model_copy(deep=True) if metadata is not None else existing.metadata
        if new_card.doc_id != new_metadata.doc_id:
            raise ValueError(
                f"Card.doc_id ({new_card.doc_id!r}) != Metadata.doc_id ({new_metadata.doc_id!r})"
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
        self._versions.clear()
        self._version_order.clear()
        self._metadata_v05.clear()
        self._artifacts.clear()

    # ============================================================
    # SETUP-05 extension API (T-S05-010)
    # ============================================================

    def save_version(self, card: RAGCard) -> RAGCard:
        """Сохранить новую версию карточки (уникальность по (doc_id, card_version)).

        Raises:
            CardAlreadyExistsError: версия (doc_id, card_version) уже сохранена.
        """
        key = (card.doc_id, card.card_version)
        if key in self._versions:
            raise CardAlreadyExistsError(f"{card.doc_id}@{card.card_version}")
        self._versions[key] = card.model_copy(deep=True)
        self._version_order.setdefault(card.doc_id, []).append(card.card_version)
        return card.model_copy(deep=True)

    def get_version(self, doc_id: str, card_version: str) -> RAGCard:
        key = (doc_id, card_version)
        if key not in self._versions:
            raise CardNotFoundError(f"{doc_id}@{card_version}")
        return self._versions[key].model_copy(deep=True)

    def list_versions(self, doc_id: str) -> list[str]:
        """Список card_version в порядке добавления (старая → новая)."""
        return list(self._version_order.get(doc_id, []))

    def latest_version(self, doc_id: str) -> RAGCard | None:
        versions = self._version_order.get(doc_id)
        if not versions:
            return None
        return self._versions[(doc_id, versions[-1])].model_copy(deep=True)

    def save_metadata(self, metadata: RAGCardMetadataDTO) -> RAGCardMetadataDTO:
        """Сохранить front matter metadata. Last-write-wins по (doc_id, card_version)."""
        key = (metadata.doc_id, metadata.card_version)
        self._metadata_v05[key] = metadata.model_copy(deep=True)
        return metadata.model_copy(deep=True)

    def get_metadata(self, doc_id: str, card_version: str) -> RAGCardMetadataDTO:
        key = (doc_id, card_version)
        if key not in self._metadata_v05:
            raise CardNotFoundError(f"metadata for {doc_id}@{card_version}")
        return self._metadata_v05[key].model_copy(deep=True)

    def attach_artifact(
        self,
        *,
        doc_id: str,
        card_version: str,
        artifact_id: str,
        artifact_type: str = "markdown",
    ) -> None:
        """Прикрепить artifact (e.g. Markdown blob ID) к версии карточки."""
        key = (doc_id, card_version)
        self._artifacts.setdefault(key, []).append((artifact_id, artifact_type))

    def list_artifacts(self, doc_id: str, card_version: str) -> list[tuple[str, str]]:
        return list(self._artifacts.get((doc_id, card_version), []))

    def list_for_setup_job(
        self,
        setup_job_id: str,
        *,
        doc_type: DocType | None = None,
        status: CardStatus | None = None,
        confidence_level: str | None = None,
        source_document_id: str | None = None,
    ) -> list[RAGCard]:
        """SETUP-05 фильтрованный list по версиям.

        Возвращает latest версию каждой карточки, удовлетворяющей фильтрам.
        Используется API endpoint GET /rag-cards.
        """
        result: list[RAGCard] = []
        for doc_id, versions in self._version_order.items():
            if not versions:
                continue
            card = self._versions[(doc_id, versions[-1])]
            if card.setup_job_id != setup_job_id:
                continue
            if doc_type is not None and card.doc_type != doc_type:
                continue
            if status is not None and card.status != status:
                continue
            if confidence_level is not None and card.confidence_level != confidence_level:
                continue
            if (
                source_document_id is not None
                and source_document_id not in card.source_document_ids
            ):
                continue
            result.append(card.model_copy(deep=True))
        return result

    # ----- Snapshot persistence (dev-only) -----

    def snapshot(self) -> dict[str, object]:
        return {
            "legacy_store": {
                doc_id: {
                    "setup_job_id": record.setup_job_id,
                    "card": record.card.model_dump(mode="json"),
                    "metadata": record.metadata.model_dump(mode="json"),
                    "section_id": record.section_id,
                    "history": list(record.history),
                }
                for doc_id, record in self._store.items()
            },
            "versions": {
                f"{doc_id}|{version}": card.model_dump(mode="json")
                for (doc_id, version), card in self._versions.items()
            },
            "version_order": {
                doc_id: list(versions) for doc_id, versions in self._version_order.items()
            },
            "metadata_v05": {
                f"{doc_id}|{version}": meta.model_dump(mode="json")
                for (doc_id, version), meta in self._metadata_v05.items()
            },
            "artifacts": {
                f"{doc_id}|{version}": list(items)
                for (doc_id, version), items in self._artifacts.items()
            },
        }

    def restore(self, data: dict[str, object]) -> None:
        self.clear()
        legacy_store = data.get("legacy_store", {})
        if isinstance(legacy_store, dict):
            for doc_id, raw in legacy_store.items():
                if not isinstance(raw, dict):
                    continue
                self._store[doc_id] = CardRecord(
                    setup_job_id=str(raw.get("setup_job_id", "")),
                    card=RAGCard.model_validate(raw.get("card", {})),
                    metadata=RAGMetadata.model_validate(raw.get("metadata", {})),
                    section_id=raw.get("section_id"),
                    history=list(raw.get("history", [])),
                )
        versions = data.get("versions", {})
        if isinstance(versions, dict):
            for key, raw in versions.items():
                if "|" not in key:
                    continue
                doc_id, version = key.split("|", 1)
                self._versions[(doc_id, version)] = RAGCard.model_validate(raw)
        version_order = data.get("version_order", {})
        if isinstance(version_order, dict):
            for doc_id, vlist in version_order.items():
                if isinstance(vlist, list):
                    self._version_order[doc_id] = [v for v in vlist if isinstance(v, str)]
        metadata_v05 = data.get("metadata_v05", {})
        if isinstance(metadata_v05, dict):
            for key, raw in metadata_v05.items():
                if "|" not in key:
                    continue
                doc_id, version = key.split("|", 1)
                self._metadata_v05[(doc_id, version)] = RAGCardMetadataDTO.model_validate(raw)
        artifacts = data.get("artifacts", {})
        if isinstance(artifacts, dict):
            for key, items in artifacts.items():
                if "|" not in key:
                    continue
                doc_id, version = key.split("|", 1)
                if isinstance(items, list):
                    self._artifacts[(doc_id, version)] = [
                        (str(t[0]), str(t[1]))
                        for t in items
                        if isinstance(t, (list, tuple)) and len(t) >= 2
                    ]

    @staticmethod
    def _clone(record: CardRecord) -> CardRecord:
        return CardRecord(
            setup_job_id=record.setup_job_id,
            card=record.card.model_copy(deep=True),
            metadata=record.metadata.model_copy(deep=True),
            section_id=record.section_id,
            history=list(record.history),
        )
