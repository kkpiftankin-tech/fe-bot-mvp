"""Source Registry Service (SVC-06).

Хранит реестр SourceDocumentDTO с дедупликацией по checksum внутри setup_job_id.
В S2 — in-memory; PostgreSQL подменится в INF-002.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-09,
docs/02-system/features/SETUP-01-setup-wizard.md §11.2.
"""

from __future__ import annotations

from typing import Protocol

from schemas.setup.source_document import SourceDocument, SourceDocumentStatus


class SourceDocumentNotFoundError(LookupError):
    def __init__(self, source_document_id: str) -> None:
        self.source_document_id = source_document_id
        super().__init__(f"Source document not found: {source_document_id}")


class SourceRegistry(Protocol):
    """Контракт реестра."""

    def add(self, document: SourceDocument) -> None: ...

    def get(self, source_document_id: str) -> SourceDocument: ...

    def find_by_checksum(self, setup_job_id: str, checksum: str) -> SourceDocument | None: ...

    def list_for_job(self, setup_job_id: str) -> list[SourceDocument]: ...

    def update(self, document: SourceDocument) -> None: ...

    def remove(self, source_document_id: str) -> SourceDocument:
        """Soft-delete: ставит status=REMOVED, освобождает дедуп-ключ.

        SETUP-02 / T-S02-014. Возвращает обновлённый документ.
        """
        ...


class InMemorySourceRegistry:
    """In-memory реализация (S2/MVP).

    Дедуп ключ: (setup_job_id, checksum).
    """

    def __init__(self) -> None:
        self._by_id: dict[str, SourceDocument] = {}
        self._by_checksum: dict[tuple[str, str], str] = {}
        # ordered list of source_document_ids per job for stable listing
        self._order: dict[str, list[str]] = {}

    def add(self, document: SourceDocument) -> None:
        key = (document.setup_job_id, document.checksum)
        if key in self._by_checksum:
            existing_id = self._by_checksum[key]
            raise DuplicateDocumentError(
                setup_job_id=document.setup_job_id,
                checksum=document.checksum,
                existing_source_document_id=existing_id,
            )
        self._by_id[document.source_document_id] = document.model_copy(deep=True)
        self._by_checksum[key] = document.source_document_id
        self._order.setdefault(document.setup_job_id, []).append(document.source_document_id)

    def get(self, source_document_id: str) -> SourceDocument:
        if source_document_id not in self._by_id:
            raise SourceDocumentNotFoundError(source_document_id)
        return self._by_id[source_document_id].model_copy(deep=True)

    def find_by_checksum(self, setup_job_id: str, checksum: str) -> SourceDocument | None:
        existing_id = self._by_checksum.get((setup_job_id, checksum))
        if existing_id is None:
            return None
        return self._by_id[existing_id].model_copy(deep=True)

    def list_for_job(self, setup_job_id: str) -> list[SourceDocument]:
        ids = self._order.get(setup_job_id, [])
        return [self._by_id[i].model_copy(deep=True) for i in ids]

    def update(self, document: SourceDocument) -> None:
        if document.source_document_id not in self._by_id:
            raise SourceDocumentNotFoundError(document.source_document_id)
        # Не позволяем менять checksum через update — это сменит дедуп-ключ.
        old = self._by_id[document.source_document_id]
        if old.checksum != document.checksum:
            raise ValueError("Cannot change checksum via update()")
        self._by_id[document.source_document_id] = document.model_copy(deep=True)

    def remove(self, source_document_id: str) -> SourceDocument:
        """Soft-delete (T-S02-014).

        - status → REMOVED.
        - дедуп-ключ (setup_job_id, checksum) освобождается → можно re-upload
          тот же файл после удаления.
        - запись остаётся в `_by_id` для audit и list_for_job (с фильтром).
        - идемпотентность: повторный вызов с тем же id возвращает уже REMOVED
          документ без повторного raise.
        """
        from schemas.setup.source_document import SourceDocumentStatus

        if source_document_id not in self._by_id:
            raise SourceDocumentNotFoundError(source_document_id)
        old = self._by_id[source_document_id]
        if old.status == SourceDocumentStatus.REMOVED:
            return old.model_copy(deep=True)
        # Освободить дедуп-ключ.
        self._by_checksum.pop((old.setup_job_id, old.checksum), None)
        updated = old.model_copy(update={"status": SourceDocumentStatus.REMOVED})
        self._by_id[source_document_id] = updated
        return updated.model_copy(deep=True)

    def clear(self) -> None:
        """Для тестов."""
        self._by_id.clear()
        self._by_checksum.clear()
        self._order.clear()

    # ----- Snapshot persistence (dev-only JSON dump) -----

    def snapshot(self) -> dict[str, object]:
        return {
            "documents": {sid: d.model_dump(mode="json") for sid, d in self._by_id.items()},
            "order": {jid: list(ids) for jid, ids in self._order.items()},
        }

    def restore(self, data: dict[str, object]) -> None:
        self.clear()
        documents = data.get("documents", {})
        order = data.get("order", {})
        if isinstance(documents, dict):
            for sid, raw in documents.items():
                doc = SourceDocument.model_validate(raw)
                self._by_id[sid] = doc
                key = (doc.setup_job_id, doc.checksum)
                if doc.status != SourceDocumentStatus.REMOVED:
                    self._by_checksum[key] = sid
        if isinstance(order, dict):
            for jid, ids in order.items():
                self._order[jid] = [i for i in ids if isinstance(i, str)]


class DuplicateDocumentError(ValueError):
    """Документ с таким же checksum уже зарегистрирован в этом setup_job_id."""

    def __init__(
        self,
        *,
        setup_job_id: str,
        checksum: str,
        existing_source_document_id: str,
    ) -> None:
        self.setup_job_id = setup_job_id
        self.checksum = checksum
        self.existing_source_document_id = existing_source_document_id
        super().__init__(
            f"Duplicate document detected (checksum={checksum[:16]}…) "
            f"already registered as {existing_source_document_id}"
        )
