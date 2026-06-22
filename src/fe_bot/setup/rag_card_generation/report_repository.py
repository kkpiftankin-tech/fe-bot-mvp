"""CardGenerationReportRepository (SETUP-05 / T-S05-012).

Хранит CardGenerationReportDTO. Уникальность по ``generation_job_id`` —
повторный ``save`` для существующего job перезаписывает (last-write-wins).

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.rag_card_generation_report import CardGenerationReportDTO


class CardGenerationReportNotFoundError(LookupError):
    def __init__(self, generation_report_id: str) -> None:
        self.generation_report_id = generation_report_id
        super().__init__(f"CardGenerationReport not found: {generation_report_id}")


class CardGenerationReportRepository(Protocol):
    def save(self, report: CardGenerationReportDTO) -> None: ...

    def get(self, generation_report_id: str) -> CardGenerationReportDTO: ...

    def get_for_job(self, generation_job_id: str) -> CardGenerationReportDTO | None: ...

    def list_for_setup_job(
        self, setup_job_id: str, *, job_id_filter: str | None = None
    ) -> list[CardGenerationReportDTO]: ...


class InMemoryCardGenerationReportRepository:
    """In-memory + thread-safe + last-write-wins per generation_job_id."""

    def __init__(self) -> None:
        # generation_report_id → DTO
        self._by_id: dict[str, CardGenerationReportDTO] = {}
        # generation_job_id → generation_report_id (latest)
        self._by_job: dict[str, str] = {}
        self._lock = threading.Lock()

    def save(self, report: CardGenerationReportDTO) -> None:
        with self._lock:
            old_id = self._by_job.get(report.generation_job_id)
            if old_id is not None and old_id != report.generation_report_id:
                self._by_id.pop(old_id, None)
            self._by_id[report.generation_report_id] = report
            self._by_job[report.generation_job_id] = report.generation_report_id

    def get(self, generation_report_id: str) -> CardGenerationReportDTO:
        with self._lock:
            if generation_report_id not in self._by_id:
                raise CardGenerationReportNotFoundError(generation_report_id)
            return self._by_id[generation_report_id]

    def get_for_job(self, generation_job_id: str) -> CardGenerationReportDTO | None:
        with self._lock:
            report_id = self._by_job.get(generation_job_id)
            if report_id is None:
                return None
            return self._by_id[report_id]

    def list_for_setup_job(
        self, setup_job_id: str, *, job_id_filter: str | None = None
    ) -> list[CardGenerationReportDTO]:
        """Возвращает reports. ``setup_job_id`` параметр зарезервирован для
        будущих расширений (когда добавим setup_job_id в DTO).
        Текущая реализация фильтрует по optional ``job_id_filter``.
        """
        with self._lock:
            reports = list(self._by_id.values())
        if job_id_filter is not None:
            reports = [r for r in reports if r.generation_job_id == job_id_filter]
        return reports

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_job.clear()

    # ----- Snapshot persistence -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {rid: r.model_dump(mode="json") for rid, r in self._by_id.items()}

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_job.clear()
            for raw in data.values():
                report = CardGenerationReportDTO.model_validate(raw)
                self._by_id[report.generation_report_id] = report
                self._by_job[report.generation_job_id] = report.generation_report_id
