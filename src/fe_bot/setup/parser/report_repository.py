"""DocumentParseReportRepository (SETUP-04 / T-S04-009).

Хранит один отчёт на каждую (parse_job_id, source_document_id) пару.
Повторный `save` для существующей пары — перезапись (последний report
актуален; downstream-аудит может смотреть append-only EventBus).
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.parse_report import DocumentParseReport


class ParseReportNotFoundError(LookupError):
    def __init__(self, parse_report_id: str) -> None:
        self.parse_report_id = parse_report_id
        super().__init__(f"DocumentParseReport not found: {parse_report_id}")


class DocumentParseReportRepository(Protocol):
    def save(self, report: DocumentParseReport) -> None: ...

    def get(self, parse_report_id: str) -> DocumentParseReport: ...

    def get_for_document_in_job(
        self, parse_job_id: str, source_document_id: str
    ) -> DocumentParseReport | None: ...

    def list_for_job(self, parse_job_id: str) -> list[DocumentParseReport]: ...


class InMemoryDocumentParseReportRepository:
    """In-memory реализация. Unique constraint: (parse_job_id, source_document_id)."""

    def __init__(self) -> None:
        self._by_id: dict[str, DocumentParseReport] = {}
        # (parse_job_id, source_document_id) → parse_report_id
        self._by_pair: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def save(self, report: DocumentParseReport) -> None:
        with self._lock:
            pair = (report.parse_job_id, report.source_document_id)
            # Если для пары уже есть report — удаляем старый id из _by_id.
            old_id = self._by_pair.get(pair)
            if old_id is not None and old_id != report.parse_report_id:
                self._by_id.pop(old_id, None)
            self._by_id[report.parse_report_id] = report.model_copy(deep=True)
            self._by_pair[pair] = report.parse_report_id

    def get(self, parse_report_id: str) -> DocumentParseReport:
        with self._lock:
            if parse_report_id not in self._by_id:
                raise ParseReportNotFoundError(parse_report_id)
            return self._by_id[parse_report_id].model_copy(deep=True)

    def get_for_document_in_job(
        self, parse_job_id: str, source_document_id: str
    ) -> DocumentParseReport | None:
        with self._lock:
            report_id = self._by_pair.get((parse_job_id, source_document_id))
            if report_id is None:
                return None
            return self._by_id[report_id].model_copy(deep=True)

    def list_for_job(self, parse_job_id: str) -> list[DocumentParseReport]:
        with self._lock:
            return [
                r.model_copy(deep=True)
                for r in self._by_id.values()
                if r.parse_job_id == parse_job_id
            ]

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_pair.clear()
