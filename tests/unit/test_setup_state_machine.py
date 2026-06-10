"""Тесты SetupOrchestrator (T-S01-008)."""

from __future__ import annotations

import pytest
from schemas.setup.rag_setup_job import InvalidTransitionError, SetupJobStatus

from fe_bot.setup.events import EventBus
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.repository import (
    InMemoryJobRepository,
    JobNotFoundError,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def orchestrator() -> tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]:
    repo = InMemoryJobRepository()
    bus = EventBus()
    return SetupOrchestrator(repo, bus), repo, bus


class TestCreateJob:
    def test_creates_job_in_draft(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, repo, _ = orchestrator
        job = svc.create_job(user_id="u1", project_name="My KB")
        assert job.status == SetupJobStatus.DRAFT
        assert job.user_id == "u1"
        assert job.project_name == "My KB"
        assert job.setup_job_id.startswith("setup_")
        assert repo.exists(job.setup_job_id)

    def test_emits_created_event(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, bus = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        events = bus.history(job.setup_job_id)
        assert len(events) == 1
        assert events[0].event_type == "setup.job.created"
        assert events[0].progress_percent == 0.0

    def test_create_returns_independent_copies(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        # Изменение возвращённого объекта не должно затронуть хранилище.
        svc, _, _ = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        job.project_name = "Mutated"
        fetched = svc.get_job(job.setup_job_id)
        assert fetched.project_name == "Test KB"


class TestAdvance:
    def test_advances_through_happy_path(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, bus = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        path = [
            SetupJobStatus.FILES_UPLOADED,
            SetupJobStatus.PARSING,
            SetupJobStatus.SECTIONS_EXTRACTED,
            SetupJobStatus.RAG_CARDS_GENERATING,
            SetupJobStatus.METADATA_VALIDATING,
            SetupJobStatus.CHUNKING,
            SetupJobStatus.EMBEDDING,
            SetupJobStatus.INDEXING,
            SetupJobStatus.RETRIEVAL_TESTING,
            SetupJobStatus.PUBLISHING,
            SetupJobStatus.READY,
        ]
        for status in path:
            svc.advance(job.setup_job_id, status)
        final = svc.get_job(job.setup_job_id)
        assert final.status == SetupJobStatus.READY
        assert final.progress_percent == 100.0
        assert final.finished_at is not None

        events = bus.history(job.setup_job_id)
        # 1 created + 11 transitions
        assert len(events) == 12
        assert events[-1].event_type == "setup.kb.ready"
        assert events[-1].progress_percent == 100.0

    def test_advance_invalid_transition_raises(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, _ = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        with pytest.raises(InvalidTransitionError):
            svc.advance(job.setup_job_id, SetupJobStatus.READY)

    def test_advance_unknown_job_raises(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, _ = orchestrator
        with pytest.raises(JobNotFoundError):
            svc.advance("nonexistent", SetupJobStatus.FILES_UPLOADED)

    def test_advance_sets_current_step(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, _ = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        svc.advance(job.setup_job_id, SetupJobStatus.FILES_UPLOADED)
        updated = svc.get_job(job.setup_job_id)
        assert updated.current_step == "files_uploaded"

    def test_advance_emits_review_required_event(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, bus = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        for s in [
            SetupJobStatus.FILES_UPLOADED,
            SetupJobStatus.PARSING,
            SetupJobStatus.SECTIONS_EXTRACTED,
            SetupJobStatus.RAG_CARDS_GENERATING,
            SetupJobStatus.METADATA_VALIDATING,
        ]:
            svc.advance(job.setup_job_id, s)
        svc.advance(job.setup_job_id, SetupJobStatus.REVIEW_REQUIRED)
        events = bus.history(job.setup_job_id)
        assert events[-1].event_type == "setup.review.required"


class TestCancel:
    def test_cancel_draft_job(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, _ = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        cancelled = svc.cancel_job(job.setup_job_id)
        assert cancelled.status == SetupJobStatus.CANCELLED
        assert cancelled.finished_at is not None

    def test_cancel_is_idempotent(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, bus = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        svc.cancel_job(job.setup_job_id)
        svc.cancel_job(job.setup_job_id)  # должно быть no-op
        cancelled_events = [
            e for e in bus.history(job.setup_job_id)
            if e.event_type == "setup.job.cancelled"
        ]
        assert len(cancelled_events) == 1

    def test_cancel_mid_pipeline(
        self, orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus]
    ) -> None:
        svc, _, _ = orchestrator
        job = svc.create_job(user_id="u1", project_name="Test KB")
        svc.advance(job.setup_job_id, SetupJobStatus.FILES_UPLOADED)
        svc.advance(job.setup_job_id, SetupJobStatus.PARSING)
        cancelled = svc.cancel_job(job.setup_job_id)
        assert cancelled.status == SetupJobStatus.CANCELLED


class TestProgressMapping:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (SetupJobStatus.DRAFT, 0.0),
            (SetupJobStatus.PARSING, 15.0),
            (SetupJobStatus.CHUNKING, 65.0),
            (SetupJobStatus.READY, 100.0),
        ],
    )
    def test_progress_per_status(
        self,
        orchestrator: tuple[SetupOrchestrator, InMemoryJobRepository, EventBus],
        status: SetupJobStatus,
        expected: float,
    ) -> None:
        from fe_bot.setup.orchestrator import _PROGRESS_PER_STATUS

        assert _PROGRESS_PER_STATUS[status] == expected
