"""ValidationRunRepository (SETUP-07 / T-S07-005).

История прогонов валидации по setup_job. Каждый прогон — отдельная запись.

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.validation_run import ValidationRunDTO


class ValidationRunNotFoundError(KeyError):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"ValidationRun {run_id!r} not found")


class ValidationRunRepository(Protocol):
    def add(self, run: ValidationRunDTO) -> ValidationRunDTO: ...

    def update(self, run: ValidationRunDTO) -> ValidationRunDTO: ...

    def get(self, run_id: str) -> ValidationRunDTO: ...

    def list_for_job(self, setup_job_id: str) -> list[ValidationRunDTO]: ...

    def latest_for_job(self, setup_job_id: str) -> ValidationRunDTO | None: ...


class InMemoryValidationRunRepository:
    """In-memory + thread-safe."""

    def __init__(self) -> None:
        self._by_id: dict[str, ValidationRunDTO] = {}
        # Ordered by insertion (used for latest_for_job).
        self._order: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def add(self, run: ValidationRunDTO) -> ValidationRunDTO:
        with self._lock:
            self._by_id[run.validation_run_id] = run
            self._order.setdefault(run.setup_job_id, []).append(run.validation_run_id)
            return run

    def update(self, run: ValidationRunDTO) -> ValidationRunDTO:
        with self._lock:
            if run.validation_run_id not in self._by_id:
                raise ValidationRunNotFoundError(run.validation_run_id)
            self._by_id[run.validation_run_id] = run
            return run

    def get(self, run_id: str) -> ValidationRunDTO:
        with self._lock:
            try:
                return self._by_id[run_id]
            except KeyError as exc:
                raise ValidationRunNotFoundError(run_id) from exc

    def list_for_job(self, setup_job_id: str) -> list[ValidationRunDTO]:
        with self._lock:
            ids = self._order.get(setup_job_id, [])
            return [self._by_id[i] for i in ids]

    def latest_for_job(self, setup_job_id: str) -> ValidationRunDTO | None:
        with self._lock:
            ids = self._order.get(setup_job_id, [])
            if not ids:
                return None
            return self._by_id[ids[-1]]

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._order.clear()

    # ----- Snapshot -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                rid: r.model_dump(mode="json") for rid, r in self._by_id.items()
            }

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._by_id.clear()
            self._order.clear()
            for rid, raw in data.items():
                run = ValidationRunDTO.model_validate(raw)
                self._by_id[rid] = run
                self._order.setdefault(run.setup_job_id, []).append(rid)
