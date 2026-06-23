"""ValidationReportRepository (SETUP-07 / T-S07-004).

Хранит persisted ValidationReports. Latest report per (setup_job_id, doc_id)
доступен через get_latest; полная история — через list_for_card.

Идемпотентность не нужна на уровне репозитория — каждый run создаёт новый
report с уникальным validation_report_id.

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.validation_report import ValidationReport


class ValidationReportNotFoundError(KeyError):
    def __init__(self, report_id: str) -> None:
        self.report_id = report_id
        super().__init__(f"ValidationReport {report_id!r} not found")


class ValidationReportRepository(Protocol):
    def save(self, report: ValidationReport) -> ValidationReport: ...

    def get(self, report_id: str) -> ValidationReport: ...

    def get_latest(self, setup_job_id: str, doc_id: str) -> ValidationReport | None: ...

    def list_for_job(self, setup_job_id: str) -> list[ValidationReport]: ...

    def list_for_card(self, setup_job_id: str, doc_id: str) -> list[ValidationReport]: ...

    def list_for_run(self, validation_run_id: str) -> list[ValidationReport]: ...


class InMemoryValidationReportRepository:
    """In-memory + thread-safe."""

    def __init__(self) -> None:
        self._by_id: dict[str, ValidationReport] = {}
        # (setup_job_id, doc_id) -> ordered list of report_ids
        self._by_card: dict[tuple[str, str], list[str]] = {}
        self._lock = threading.Lock()

    def save(self, report: ValidationReport) -> ValidationReport:
        with self._lock:
            self._by_id[report.validation_report_id] = report
            if report.setup_job_id:
                key = (report.setup_job_id, report.target_id)
                self._by_card.setdefault(key, []).append(report.validation_report_id)
            return report

    def get(self, report_id: str) -> ValidationReport:
        with self._lock:
            try:
                return self._by_id[report_id]
            except KeyError as exc:
                raise ValidationReportNotFoundError(report_id) from exc

    def get_latest(self, setup_job_id: str, doc_id: str) -> ValidationReport | None:
        with self._lock:
            key = (setup_job_id, doc_id)
            ids = self._by_card.get(key, [])
            if not ids:
                return None
            return self._by_id[ids[-1]]

    def list_for_job(self, setup_job_id: str) -> list[ValidationReport]:
        with self._lock:
            return [
                r for r in self._by_id.values() if r.setup_job_id == setup_job_id
            ]

    def list_for_card(self, setup_job_id: str, doc_id: str) -> list[ValidationReport]:
        with self._lock:
            key = (setup_job_id, doc_id)
            ids = self._by_card.get(key, [])
            return [self._by_id[i] for i in ids]

    def list_for_run(self, validation_run_id: str) -> list[ValidationReport]:
        with self._lock:
            return [
                r
                for r in self._by_id.values()
                if r.validation_run_id == validation_run_id
            ]

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_card.clear()

    # ----- Snapshot -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                rid: r.model_dump(mode="json") for rid, r in self._by_id.items()
            }

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_card.clear()
            for rid, raw in data.items():
                report = ValidationReport.model_validate(raw)
                self._by_id[rid] = report
                if report.setup_job_id:
                    key = (report.setup_job_id, report.target_id)
                    self._by_card.setdefault(key, []).append(rid)
