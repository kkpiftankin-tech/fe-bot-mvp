"""Тесты схемы RAGSetupJob (T-S01-001)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.rag_setup_job import (
    InvalidTransitionError,
    RAGSetupJob,
    SetupJobStatus,
)

pytestmark = pytest.mark.unit


def _make_job(**overrides: object) -> RAGSetupJob:
    defaults: dict[str, object] = {
        "setup_job_id": "setup_001",
        "user_id": "user_42",
        "project_name": "Naval Radar KB",
    }
    defaults.update(overrides)
    return RAGSetupJob.model_validate(defaults)


class TestRAGSetupJobSchema:
    def test_minimal_valid_job(self) -> None:
        job = _make_job()
        assert job.status == SetupJobStatus.DRAFT
        assert job.progress_percent == 0.0
        assert job.source_document_ids == []

    def test_all_15_statuses_present(self) -> None:
        assert {s.value for s in SetupJobStatus} == {
            "draft",
            "files_uploaded",
            "parsing",
            "sections_extracted",
            "rag_cards_generating",
            "metadata_validating",
            "review_required",
            "chunking",
            "embedding",
            "indexing",
            "retrieval_testing",
            "publishing",
            "ready",
            "failed",
            "cancelled",
        }

    def test_progress_percent_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_job(progress_percent=-1.0)
        with pytest.raises(ValidationError):
            _make_job(progress_percent=101.0)

    def test_progress_percent_boundary_values(self) -> None:
        assert _make_job(progress_percent=0.0).progress_percent == 0.0
        assert _make_job(progress_percent=100.0).progress_percent == 100.0

    def test_project_name_min_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_job(project_name="ab")

    def test_project_name_stripped(self) -> None:
        job = _make_job(project_name="  My KB  ")
        assert job.project_name == "My KB"

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            RAGSetupJob.model_validate(
                {
                    "setup_job_id": "s1",
                    "user_id": "u1",
                    "project_name": "test",
                    "unknown_field": "x",
                }
            )

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_job(error_count=-1)
        with pytest.raises(ValidationError):
            _make_job(warning_count=-1)


class TestStateMachine:
    def test_draft_can_transition_to_files_uploaded(self) -> None:
        job = _make_job()
        job.transition_to(SetupJobStatus.FILES_UPLOADED)
        assert job.status == SetupJobStatus.FILES_UPLOADED

    def test_ready_cannot_transition_to_parsing(self) -> None:
        # AC: невалидные переходы (`ready → parsing`) отвергаются
        job = _make_job(status=SetupJobStatus.READY)
        with pytest.raises(InvalidTransitionError) as exc:
            job.transition_to(SetupJobStatus.PARSING)
        assert exc.value.from_status == SetupJobStatus.READY
        assert exc.value.to_status == SetupJobStatus.PARSING

    def test_full_happy_path_transition(self) -> None:
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
        job = _make_job()
        for step in path:
            job.transition_to(step)
        assert job.status == SetupJobStatus.READY

    def test_failed_allows_rerun_from_step(self) -> None:
        # A4: rerun from failed step
        job = _make_job(status=SetupJobStatus.FAILED)
        job.transition_to(SetupJobStatus.PARSING)
        assert job.status == SetupJobStatus.PARSING

    def test_cancelled_is_terminal(self) -> None:
        job = _make_job(status=SetupJobStatus.CANCELLED)
        for target in SetupJobStatus:
            if target == SetupJobStatus.CANCELLED:
                continue
            with pytest.raises(InvalidTransitionError):
                job.transition_to(target)

    def test_review_required_can_regenerate(self) -> None:
        job = _make_job(status=SetupJobStatus.REVIEW_REQUIRED)
        job.transition_to(SetupJobStatus.RAG_CARDS_GENERATING)
        assert job.status == SetupJobStatus.RAG_CARDS_GENERATING

    def test_can_transition_to_returns_bool(self) -> None:
        job = _make_job()
        assert job.can_transition_to(SetupJobStatus.FILES_UPLOADED) is True
        assert job.can_transition_to(SetupJobStatus.READY) is False

    def test_is_terminal_property(self) -> None:
        assert _make_job(status=SetupJobStatus.READY).is_terminal is True
        assert _make_job(status=SetupJobStatus.CANCELLED).is_terminal is True
        assert _make_job(status=SetupJobStatus.DRAFT).is_terminal is False

    def test_validate_assignment_blocks_direct_invalid_status(self) -> None:
        # При config.validate_assignment=True прямое присваивание тоже валидируется.
        # Здесь проверяем, что status хотя бы остаётся валидным enum.
        job = _make_job()
        with pytest.raises(ValidationError):
            job.status = "invalid_status"  # type: ignore[assignment]


class TestSerialization:
    def test_round_trip_json(self) -> None:
        job = _make_job(
            status=SetupJobStatus.CHUNKING,
            progress_percent=42.5,
            source_document_ids=["src_1", "src_2"],
            started_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        )
        payload = job.model_dump_json()
        restored = RAGSetupJob.model_validate_json(payload)
        assert restored == job
