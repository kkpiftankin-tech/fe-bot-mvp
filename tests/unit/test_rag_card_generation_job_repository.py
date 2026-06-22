"""Unit-тесты RAGCardGenerationJobRepository (SETUP-05 / T-S05-008)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.rag_card_generation_job import (
    RAGCardGenerationJob,
    RAGCardGenerationJobStatus,
)

from fe_bot.setup.rag_card_generation.job_repository import (
    DuplicateRAGCardGenerationJobError,
    InMemoryRAGCardGenerationJobRepository,
    RAGCardGenerationJobNotFoundError,
)

pytestmark = pytest.mark.unit


def _job(
    *,
    generation_job_id: str = "gen_001",
    setup_job_id: str = "setup_001",
    status: RAGCardGenerationJobStatus = RAGCardGenerationJobStatus.CREATED,
) -> RAGCardGenerationJob:
    now = datetime(2026, 6, 19, tzinfo=UTC)
    return RAGCardGenerationJob(
        generation_job_id=generation_job_id,
        setup_job_id=setup_job_id,
        requested_by="user_001",
        status=status,
        created_at=now,
        updated_at=now,
    )


class TestCreateGetUpdate:
    def test_create_and_get(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        repo.create(_job())
        loaded = repo.get("gen_001")
        assert loaded.generation_job_id == "gen_001"
        assert loaded.status == RAGCardGenerationJobStatus.CREATED

    def test_duplicate_raises(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        repo.create(_job())
        with pytest.raises(DuplicateRAGCardGenerationJobError):
            repo.create(_job())

    def test_get_unknown_raises(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        with pytest.raises(RAGCardGenerationJobNotFoundError):
            repo.get("gen_missing")

    def test_update(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        repo.create(_job())
        job = repo.get("gen_001")
        job.transition_to(RAGCardGenerationJobStatus.QUEUED)
        repo.update(job)
        assert repo.get("gen_001").status == RAGCardGenerationJobStatus.QUEUED

    def test_update_unknown_raises(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        with pytest.raises(RAGCardGenerationJobNotFoundError):
            repo.update(_job(generation_job_id="ghost"))


class TestActiveJob:
    def test_no_active(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        repo.create(
            _job(
                generation_job_id="gen_a",
                status=RAGCardGenerationJobStatus.CREATED,
            )
        )
        # Переводим в terminal.
        job = repo.get("gen_a")
        job.transition_to(RAGCardGenerationJobStatus.CANCELLED)
        repo.update(job)
        assert repo.get_active_for_setup_job("setup_001") is None

    def test_active_created(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        repo.create(_job(generation_job_id="gen_a"))
        active = repo.get_active_for_setup_job("setup_001")
        assert active is not None
        assert active.generation_job_id == "gen_a"

    def test_active_skips_other_setup_job(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        repo.create(_job(generation_job_id="gen_a", setup_job_id="setup_x"))
        assert repo.get_active_for_setup_job("setup_other") is None


class TestSnapshotRestore:
    def test_roundtrip(self) -> None:
        repo = InMemoryRAGCardGenerationJobRepository()
        repo.create(_job(generation_job_id="gen_a"))
        repo.create(_job(generation_job_id="gen_b", setup_job_id="setup_002"))
        snap = repo.snapshot()

        repo2 = InMemoryRAGCardGenerationJobRepository()
        repo2.restore(snap)
        assert repo2.get("gen_a").setup_job_id == "setup_001"
        assert repo2.get("gen_b").setup_job_id == "setup_002"
