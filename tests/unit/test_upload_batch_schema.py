"""Тесты UploadBatchDTO (T-S02-001)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.upload_batch import (
    InvalidBatchTransitionError,
    UploadBatch,
    UploadBatchStatus,
)

pytestmark = pytest.mark.unit


def _now() -> datetime:
    return datetime(2026, 6, 10, 10, 0, tzinfo=UTC)


def _make_batch(**overrides: object) -> UploadBatch:
    defaults: dict[str, object] = {
        "upload_batch_id": "batch_001",
        "setup_job_id": "setup_001",
        "user_id": "u1",
        "files_total": 3,
        "created_at": _now(),
    }
    defaults.update(overrides)
    return UploadBatch.model_validate(defaults)


class TestConstruction:
    def test_minimal_batch_defaults_to_in_progress(self) -> None:
        batch = _make_batch()
        assert batch.status == UploadBatchStatus.IN_PROGRESS
        assert batch.files_uploaded == 0
        assert batch.files_rejected == 0
        assert batch.duplicates_detected == 0
        assert batch.finished_at is None
        assert batch.upload_request_id is None

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="extra"):
            UploadBatch.model_validate(
                {
                    "upload_batch_id": "x",
                    "setup_job_id": "y",
                    "user_id": "u",
                    "files_total": 0,
                    "created_at": _now(),
                    "rogue_field": "boom",
                }
            )

    def test_negative_counter_rejected(self) -> None:
        with pytest.raises(ValueError):
            _make_batch(files_uploaded=-1)


class TestCounterConsistency:
    def test_uploaded_plus_rejected_plus_duplicates_le_total(self) -> None:
        # 1 + 1 + 1 = 3 ≤ 3
        batch = _make_batch(
            files_total=3,
            files_uploaded=1,
            files_rejected=1,
            duplicates_detected=1,
        )
        assert batch.files_total == 3

    def test_counters_exceeding_total_rejected(self) -> None:
        with pytest.raises(ValueError, match="Counters inconsistent"):
            _make_batch(
                files_total=2,
                files_uploaded=2,
                files_rejected=1,
            )


class TestTransitions:
    def test_in_progress_to_completed_atomically_sets_finished_at(self) -> None:
        batch = _make_batch()
        assert batch.can_transition_to(UploadBatchStatus.COMPLETED)
        batch.transition_to(UploadBatchStatus.COMPLETED, finished_at=_now())
        assert batch.status == UploadBatchStatus.COMPLETED
        assert batch.finished_at == _now()

    def test_in_progress_to_failed_via_can_transition(self) -> None:
        batch = _make_batch()
        assert batch.can_transition_to(UploadBatchStatus.FAILED)

    def test_terminal_cannot_transition(self) -> None:
        batch = _make_batch()
        batch.transition_to(UploadBatchStatus.PARTIALLY_COMPLETED, finished_at=_now())
        assert not batch.can_transition_to(UploadBatchStatus.COMPLETED)
        with pytest.raises(InvalidBatchTransitionError):
            batch.transition_to(UploadBatchStatus.COMPLETED)

    def test_terminal_transition_auto_sets_finished_at_when_not_provided(
        self,
    ) -> None:
        batch = _make_batch()
        batch.transition_to(UploadBatchStatus.FAILED)
        assert batch.finished_at is not None
        assert batch.status == UploadBatchStatus.FAILED

    def test_invalid_transition_raises(self) -> None:
        batch = _make_batch()
        # IN_PROGRESS → IN_PROGRESS запрещён.
        with pytest.raises(InvalidBatchTransitionError):
            batch.transition_to(UploadBatchStatus.IN_PROGRESS)


class TestFinishedAtConsistency:
    def test_terminal_status_requires_finished_at(self) -> None:
        with pytest.raises(ValueError, match="finished_at"):
            _make_batch(status=UploadBatchStatus.COMPLETED, finished_at=None)

    def test_finished_at_requires_terminal_status(self) -> None:
        with pytest.raises(ValueError, match="finished_at"):
            _make_batch(status=UploadBatchStatus.IN_PROGRESS, finished_at=_now())

    def test_completed_with_finished_at_ok(self) -> None:
        batch = _make_batch(
            status=UploadBatchStatus.COMPLETED,
            finished_at=_now(),
            files_uploaded=3,
        )
        assert batch.finished_at is not None
