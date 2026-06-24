"""ChunkManifestRepository (SETUP-08 / T-S08-002).

Хранит persisted manifests per setup_job. Latest-by-setup-job через
get_latest_for_job. Каждый batch run пишет новый manifest (idempotent only
by manifest_id).

Поддерживает snapshot/restore.
"""

from __future__ import annotations

import threading
from typing import Protocol

from schemas.setup.chunk_manifest import ChunkingRunDTO, ChunkManifestDTO


class ChunkManifestNotFoundError(KeyError):
    def __init__(self, manifest_id: str) -> None:
        self.manifest_id = manifest_id
        super().__init__(f"ChunkManifest {manifest_id!r} not found")


class ChunkManifestRepository(Protocol):
    def save(self, manifest: ChunkManifestDTO) -> ChunkManifestDTO: ...

    def get(self, manifest_id: str) -> ChunkManifestDTO: ...

    def get_latest_for_job(self, setup_job_id: str) -> ChunkManifestDTO | None: ...

    def list_for_job(self, setup_job_id: str) -> list[ChunkManifestDTO]: ...

    def save_run(self, run: ChunkingRunDTO) -> ChunkingRunDTO: ...

    def list_runs_for_job(self, setup_job_id: str) -> list[ChunkingRunDTO]: ...


class InMemoryChunkManifestRepository:
    """In-memory + thread-safe."""

    def __init__(self) -> None:
        self._manifests_by_id: dict[str, ChunkManifestDTO] = {}
        self._manifests_by_job: dict[str, list[str]] = {}
        self._runs_by_id: dict[str, ChunkingRunDTO] = {}
        self._runs_by_job: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def save(self, manifest: ChunkManifestDTO) -> ChunkManifestDTO:
        with self._lock:
            self._manifests_by_id[manifest.manifest_id] = manifest
            self._manifests_by_job.setdefault(manifest.setup_job_id, []).append(
                manifest.manifest_id
            )
            return manifest

    def get(self, manifest_id: str) -> ChunkManifestDTO:
        with self._lock:
            try:
                return self._manifests_by_id[manifest_id]
            except KeyError as exc:
                raise ChunkManifestNotFoundError(manifest_id) from exc

    def get_latest_for_job(self, setup_job_id: str) -> ChunkManifestDTO | None:
        with self._lock:
            ids = self._manifests_by_job.get(setup_job_id, [])
            if not ids:
                return None
            return self._manifests_by_id[ids[-1]]

    def list_for_job(self, setup_job_id: str) -> list[ChunkManifestDTO]:
        with self._lock:
            ids = self._manifests_by_job.get(setup_job_id, [])
            return [self._manifests_by_id[i] for i in ids]

    def save_run(self, run: ChunkingRunDTO) -> ChunkingRunDTO:
        with self._lock:
            self._runs_by_id[run.chunking_run_id] = run
            self._runs_by_job.setdefault(run.setup_job_id, []).append(
                run.chunking_run_id
            )
            return run

    def list_runs_for_job(self, setup_job_id: str) -> list[ChunkingRunDTO]:
        with self._lock:
            ids = self._runs_by_job.get(setup_job_id, [])
            return [self._runs_by_id[i] for i in ids]

    def clear(self) -> None:
        with self._lock:
            self._manifests_by_id.clear()
            self._manifests_by_job.clear()
            self._runs_by_id.clear()
            self._runs_by_job.clear()

    # ----- Snapshot -----

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "manifests": {
                    mid: m.model_dump(mode="json")
                    for mid, m in self._manifests_by_id.items()
                },
                "runs": {
                    rid: r.model_dump(mode="json")
                    for rid, r in self._runs_by_id.items()
                },
            }

    def restore(self, data: dict[str, object]) -> None:
        with self._lock:
            self._manifests_by_id.clear()
            self._manifests_by_job.clear()
            self._runs_by_id.clear()
            self._runs_by_job.clear()
            manifests = data.get("manifests", {})
            if isinstance(manifests, dict):
                for mid, raw in manifests.items():
                    m = ChunkManifestDTO.model_validate(raw)
                    self._manifests_by_id[mid] = m
                    self._manifests_by_job.setdefault(m.setup_job_id, []).append(mid)
            runs = data.get("runs", {})
            if isinstance(runs, dict):
                for rid, raw in runs.items():
                    r = ChunkingRunDTO.model_validate(raw)
                    self._runs_by_id[rid] = r
                    self._runs_by_job.setdefault(r.setup_job_id, []).append(rid)
