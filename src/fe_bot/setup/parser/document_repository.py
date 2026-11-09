"""ParseJobDocumentRepository (SETUP-04 / T-S04-007).

Per-document отслеживание внутри ParseJob. Уникальный ключ — `parse_job_document_id`.
`list_pending_for_job` возвращает только статус PENDING для очереди worker'у.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.parse_job_document import (
    ParseJobDocument,
    ParseJobDocumentStatus,
)


class ParseJobDocumentNotFoundError(LookupError):
    def __init__(self, parse_job_document_id: str) -> None:
        self.parse_job_document_id = parse_job_document_id
        super().__init__(f"ParseJobDocument not found: {parse_job_document_id}")


class ParseJobDocumentRepository(Protocol):
    """Контракт хранилища ParseJobDocument."""

    def add(self, doc: ParseJobDocument) -> None: ...

    def get(self, parse_job_document_id: str) -> ParseJobDocument: ...

    def update(self, doc: ParseJobDocument) -> None: ...

    def list_for_job(self, parse_job_id: str) -> list[ParseJobDocument]: ...

    def list_pending_for_job(self, parse_job_id: str) -> list[ParseJobDocument]: ...


class InMemoryParseJobDocumentRepository:
    """In-memory реализация. Сохраняет порядок добавления для list_pending."""

    def __init__(self) -> None:
        self._store: dict[str, ParseJobDocument] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def add(self, doc: ParseJobDocument) -> None:
        with self._lock:
            stored = doc.model_copy(deep=True)
            self._store[doc.parse_job_document_id] = stored
            if doc.parse_job_document_id not in self._order:
                self._order.append(doc.parse_job_document_id)

    def get(self, parse_job_document_id: str) -> ParseJobDocument:
        with self._lock:
            if parse_job_document_id not in self._store:
                raise ParseJobDocumentNotFoundError(parse_job_document_id)
            return self._store[parse_job_document_id].model_copy(deep=True)

    def update(self, doc: ParseJobDocument) -> None:
        with self._lock:
            if doc.parse_job_document_id not in self._store:
                raise ParseJobDocumentNotFoundError(doc.parse_job_document_id)
            self._store[doc.parse_job_document_id] = doc.model_copy(deep=True)

    def list_for_job(self, parse_job_id: str) -> list[ParseJobDocument]:
        with self._lock:
            return [
                self._store[pjd_id].model_copy(deep=True)
                for pjd_id in self._order
                if self._store[pjd_id].parse_job_id == parse_job_id
            ]

    def list_pending_for_job(self, parse_job_id: str) -> list[ParseJobDocument]:
        with self._lock:
            return [
                self._store[pjd_id].model_copy(deep=True)
                for pjd_id in self._order
                if self._store[pjd_id].parse_job_id == parse_job_id
                and self._store[pjd_id].status == ParseJobDocumentStatus.PENDING
            ]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()

    # ----- Snapshot persistence (dev-only) -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "documents": {pid: d.model_dump(mode="json") for pid, d in self._store.items()},
                "order": list(self._order),
            }

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()
            documents = data.get("documents", {})
            order = data.get("order", [])
            if isinstance(documents, dict):
                for pid, raw in documents.items():
                    self._store[pid] = ParseJobDocument.model_validate(raw)
            if isinstance(order, list):
                self._order.extend(i for i in order if isinstance(i, str))
