"""Unit-тесты ParseJobRepository (T-S04-006)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest
from schemas.setup.parse_job import ParseJob, ParseJobStatus

from fe_bot.setup.parser.job_repository import (
    DuplicateParseJobError,
    InMemoryParseJobRepository,
    ParseJobNotFoundError,
)

pytestmark = pytest.mark.unit


def _job(
    *,
    parse_job_id: str = "pj_001",
    setup_job_id: str = "setup_001",
    status: ParseJobStatus = ParseJobStatus.QUEUED,
    requested_by: str = "u1",
) -> ParseJob:
    now = datetime(2026, 6, 13, 10, 0, tzinfo=UTC)
    return ParseJob(
        parse_job_id=parse_job_id,
        setup_job_id=setup_job_id,
        requested_by=requested_by,
        status=status,
        total_documents=3,
        processed_documents=0,
        failed_documents=0,
        total_sections=0,
        low_confidence_sections=0,
        created_at=now,
        updated_at=now,
    )


class TestCreate:
    def test_create_stores_job(self) -> None:
        repo = InMemoryParseJobRepository()
        repo.create(_job())
        assert repo.get("pj_001").parse_job_id == "pj_001"

    def test_create_duplicate_raises(self) -> None:
        repo = InMemoryParseJobRepository()
        repo.create(_job())
        with pytest.raises(DuplicateParseJobError):
            repo.create(_job())


class TestGetUpdate:
    def test_get_unknown_raises(self) -> None:
        repo = InMemoryParseJobRepository()
        with pytest.raises(ParseJobNotFoundError):
            repo.get("nope")

    def test_update_changes_status(self) -> None:
        repo = InMemoryParseJobRepository()
        repo.create(_job())
        updated = _job(status=ParseJobStatus.RUNNING)
        repo.update(updated)
        assert repo.get("pj_001").status == ParseJobStatus.RUNNING

    def test_update_unknown_raises(self) -> None:
        repo = InMemoryParseJobRepository()
        with pytest.raises(ParseJobNotFoundError):
            repo.update(_job())


class TestListAndActive:
    def test_list_for_setup_job(self) -> None:
        repo = InMemoryParseJobRepository()
        repo.create(_job(parse_job_id="pj_1"))
        repo.create(_job(parse_job_id="pj_2"))
        repo.create(_job(parse_job_id="pj_3", setup_job_id="other"))
        jobs = repo.list_for_setup_job("setup_001")
        ids = {j.parse_job_id for j in jobs}
        assert ids == {"pj_1", "pj_2"}

    def test_get_active_returns_running(self) -> None:
        repo = InMemoryParseJobRepository()
        repo.create(_job(parse_job_id="pj_1", status=ParseJobStatus.COMPLETED))
        repo.create(_job(parse_job_id="pj_2", status=ParseJobStatus.RUNNING))
        active = repo.get_active_for_setup_job("setup_001")
        assert active is not None
        assert active.parse_job_id == "pj_2"

    def test_get_active_none_when_no_active(self) -> None:
        repo = InMemoryParseJobRepository()
        repo.create(_job(status=ParseJobStatus.COMPLETED))
        assert repo.get_active_for_setup_job("setup_001") is None


class TestThreadSafety:
    def test_concurrent_create_same_id_only_one_succeeds(self) -> None:
        """50 параллельных create с тем же id → 1 success, 49 DuplicateError."""
        repo = InMemoryParseJobRepository()
        errors: list[Exception] = []
        successes: list[None] = []

        def attempt() -> None:
            try:
                repo.create(_job(parse_job_id="pj_race"))
                successes.append(None)
            except DuplicateParseJobError as e:
                errors.append(e)

        threads = [threading.Thread(target=attempt) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(successes) == 1
        assert len(errors) == 49
