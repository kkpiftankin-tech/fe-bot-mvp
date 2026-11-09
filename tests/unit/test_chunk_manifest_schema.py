"""Unit tests for ChunkManifestDTO + ChunkingRunDTO (SETUP-08 / T-S08-001)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.chunk_manifest import ChunkingRunDTO, ChunkManifestDTO


def _now() -> datetime:
    return datetime(2026, 6, 24, 12, 0, 0, tzinfo=UTC)


def test_manifest_minimal():
    m = ChunkManifestDTO(
        manifest_id="manifest_001",
        setup_job_id="sj1",
        created_at=_now(),
        created_by="u1",
    )
    assert m.total_chunks == 0
    assert m.by_type == {}
    assert m.chunks == []


def test_manifest_with_counts():
    m = ChunkManifestDTO(
        manifest_id="manifest_001",
        setup_job_id="sj1",
        total_chunks=9,
        by_type={"summary": 3, "definition": 3, "metadata_summary": 3},
        created_at=_now(),
        created_by="u1",
    )
    assert m.total_chunks == 9
    assert m.by_type["summary"] == 3


def test_manifest_frozen():
    m = ChunkManifestDTO(
        manifest_id="m_1",
        setup_job_id="sj1",
        created_at=_now(),
        created_by="u1",
    )
    with pytest.raises(ValidationError):
        m.total_chunks = 1  # type: ignore[misc]


def test_manifest_negative_total_rejected():
    with pytest.raises(ValidationError):
        ChunkManifestDTO(
            manifest_id="m_1",
            setup_job_id="sj1",
            total_chunks=-1,
            created_at=_now(),
            created_by="u1",
        )


def test_run_minimal():
    r = ChunkingRunDTO(
        chunking_run_id="cr_1",
        setup_job_id="sj1",
        manifest_id="m_1",
        triggered_by="u1",
        started_at=_now(),
        finished_at=_now(),
    )
    assert r.total_cards == 0
    assert r.chunks_created == 0


def test_run_with_metrics():
    r = ChunkingRunDTO(
        chunking_run_id="cr_1",
        setup_job_id="sj1",
        manifest_id="m_1",
        triggered_by="u1",
        total_cards=5,
        chunks_created=15,
        duration_ms=200,
        started_at=_now(),
        finished_at=_now(),
    )
    assert r.total_cards == 5
    assert r.chunks_created == 15
