"""Unit tests for ChunkManifestRepository (SETUP-08 / T-S08-002)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fe_bot.setup.chunking.manifest_repository import (
    ChunkManifestNotFoundError,
    InMemoryChunkManifestRepository,
)
from schemas.setup.chunk_manifest import ChunkingRunDTO, ChunkManifestDTO


def _now() -> datetime:
    return datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)


def _manifest(mid: str = "m_1", setup_job_id: str = "sj1", **kw: object) -> ChunkManifestDTO:
    defaults: dict[str, object] = {
        "manifest_id": mid,
        "setup_job_id": setup_job_id,
        "created_at": _now(),
        "created_by": "u1",
    }
    defaults.update(kw)
    return ChunkManifestDTO(**defaults)  # type: ignore[arg-type]


def _run(rid: str = "cr_1", manifest_id: str = "m_1", setup_job_id: str = "sj1") -> ChunkingRunDTO:
    return ChunkingRunDTO(
        chunking_run_id=rid,
        setup_job_id=setup_job_id,
        manifest_id=manifest_id,
        triggered_by="u1",
        started_at=_now(),
        finished_at=_now(),
    )


def test_save_and_get():
    repo = InMemoryChunkManifestRepository()
    m = _manifest()
    repo.save(m)
    assert repo.get("m_1").manifest_id == "m_1"


def test_get_missing_raises():
    repo = InMemoryChunkManifestRepository()
    with pytest.raises(ChunkManifestNotFoundError):
        repo.get("missing")


def test_get_latest_for_job():
    repo = InMemoryChunkManifestRepository()
    repo.save(_manifest("m_a"))
    repo.save(_manifest("m_b"))
    latest = repo.get_latest_for_job("sj1")
    assert latest is not None
    assert latest.manifest_id == "m_b"


def test_get_latest_returns_none_when_empty():
    repo = InMemoryChunkManifestRepository()
    assert repo.get_latest_for_job("sj_empty") is None


def test_list_for_job_filters():
    repo = InMemoryChunkManifestRepository()
    repo.save(_manifest("m_1", setup_job_id="sj1"))
    repo.save(_manifest("m_2", setup_job_id="sj2"))
    repo.save(_manifest("m_3", setup_job_id="sj1"))
    assert {m.manifest_id for m in repo.list_for_job("sj1")} == {"m_1", "m_3"}


def test_save_run_and_list():
    repo = InMemoryChunkManifestRepository()
    repo.save_run(_run("r_1"))
    repo.save_run(_run("r_2"))
    runs = repo.list_runs_for_job("sj1")
    assert {r.chunking_run_id for r in runs} == {"r_1", "r_2"}


def test_snapshot_restore_roundtrip():
    repo = InMemoryChunkManifestRepository()
    repo.save(_manifest("m_1"))
    repo.save_run(_run("r_1"))
    data = repo.snapshot()

    repo2 = InMemoryChunkManifestRepository()
    repo2.restore(data)
    assert repo2.get("m_1").manifest_id == "m_1"
    assert len(repo2.list_runs_for_job("sj1")) == 1
