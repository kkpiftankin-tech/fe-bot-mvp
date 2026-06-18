"""Тесты InMemoryBatchRegistry (T-S02-008)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.upload_batch import UploadBatch, UploadBatchStatus

from fe_bot.setup.upload.batch_registry import (
    BatchAlreadyExistsError,
    BatchNotFoundError,
    InMemoryBatchRegistry,
)

pytestmark = pytest.mark.unit


def _now() -> datetime:
    return datetime(2026, 6, 10, 10, 0, tzinfo=UTC)


def _make_batch(
    *,
    upload_batch_id: str = "batch_001",
    setup_job_id: str = "setup_001",
    user_id: str = "u1",
    upload_request_id: str | None = None,
    files_total: int = 3,
) -> UploadBatch:
    return UploadBatch(
        upload_batch_id=upload_batch_id,
        setup_job_id=setup_job_id,
        user_id=user_id,
        upload_request_id=upload_request_id,
        files_total=files_total,
        created_at=_now(),
    )


@pytest.fixture
def reg() -> InMemoryBatchRegistry:
    return InMemoryBatchRegistry()


class TestAdd:
    def test_add_then_get(self, reg: InMemoryBatchRegistry) -> None:
        batch = _make_batch()
        reg.add(batch)
        fetched = reg.get("batch_001")
        assert fetched.upload_batch_id == "batch_001"
        assert fetched.status == UploadBatchStatus.IN_PROGRESS

    def test_add_duplicate_raises(self, reg: InMemoryBatchRegistry) -> None:
        reg.add(_make_batch())
        with pytest.raises(BatchAlreadyExistsError):
            reg.add(_make_batch())

    def test_returned_record_is_deep_copy(self, reg: InMemoryBatchRegistry) -> None:
        batch = _make_batch()
        reg.add(batch)
        fetched = reg.get("batch_001")
        # Мутация локальной копии не должна задеть store.
        fetched.transition_to(UploadBatchStatus.FAILED)
        re_fetched = reg.get("batch_001")
        assert re_fetched.status == UploadBatchStatus.IN_PROGRESS


class TestGet:
    def test_get_unknown_raises(self, reg: InMemoryBatchRegistry) -> None:
        with pytest.raises(BatchNotFoundError):
            reg.get("nope")


class TestUpdate:
    def test_update_persists_changes(self, reg: InMemoryBatchRegistry) -> None:
        batch = _make_batch()
        reg.add(batch)
        # Поменяем counters + terminal status
        updated = batch.model_copy(
            update={
                "files_uploaded": 2,
                "files_rejected": 1,
            }
        )
        updated.transition_to(UploadBatchStatus.PARTIALLY_COMPLETED)
        reg.update(updated)

        re_fetched = reg.get("batch_001")
        assert re_fetched.status == UploadBatchStatus.PARTIALLY_COMPLETED
        assert re_fetched.files_uploaded == 2
        assert re_fetched.files_rejected == 1
        assert re_fetched.finished_at is not None

    def test_update_unknown_raises(self, reg: InMemoryBatchRegistry) -> None:
        with pytest.raises(BatchNotFoundError):
            reg.update(_make_batch(upload_batch_id="unknown"))


class TestListForJob:
    def test_filters_by_setup_job(self, reg: InMemoryBatchRegistry) -> None:
        reg.add(_make_batch(upload_batch_id="b1", setup_job_id="j1"))
        reg.add(_make_batch(upload_batch_id="b2", setup_job_id="j1"))
        reg.add(_make_batch(upload_batch_id="b3", setup_job_id="j2"))
        assert len(reg.list_for_job("j1")) == 2
        assert len(reg.list_for_job("j2")) == 1
        assert reg.list_for_job("nope") == []


class TestGetByRequestId:
    def test_finds_by_compound_key(self, reg: InMemoryBatchRegistry) -> None:
        reg.add(
            _make_batch(
                upload_batch_id="b1",
                setup_job_id="j1",
                upload_request_id="req_a",
            )
        )
        reg.add(
            _make_batch(
                upload_batch_id="b2",
                setup_job_id="j1",
                upload_request_id="req_b",
            )
        )
        # Same request_id, different job → not the same batch
        reg.add(
            _make_batch(
                upload_batch_id="b3",
                setup_job_id="j2",
                upload_request_id="req_a",
            )
        )

        found_a = reg.get_by_request_id("j1", "req_a")
        assert found_a is not None
        assert found_a.upload_batch_id == "b1"

        found_b = reg.get_by_request_id("j1", "req_b")
        assert found_b is not None and found_b.upload_batch_id == "b2"

        # Different job, same request_id → different batch (compound key)
        found_other = reg.get_by_request_id("j2", "req_a")
        assert found_other is not None and found_other.upload_batch_id == "b3"

    def test_returns_none_if_not_found(self, reg: InMemoryBatchRegistry) -> None:
        reg.add(_make_batch(upload_request_id="req_x"))
        assert reg.get_by_request_id("setup_001", "nope") is None
        assert reg.get_by_request_id("nope", "req_x") is None

    def test_no_request_id_not_searchable(self, reg: InMemoryBatchRegistry) -> None:
        # Batch без upload_request_id — не находится по compound key
        reg.add(_make_batch(upload_request_id=None))
        assert reg.get_by_request_id("setup_001", "anything") is None


class TestSizeClear:
    def test_size_clear(self, reg: InMemoryBatchRegistry) -> None:
        assert reg.size() == 0
        reg.add(_make_batch())
        assert reg.size() == 1
        reg.clear()
        assert reg.size() == 0
