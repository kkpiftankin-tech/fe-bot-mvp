"""Тесты InMemoryIdempotencyCache (T-S02-007)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from schemas.setup.rag_setup_job import SetupJobStatus

from fe_bot.api.setup.dto import UploadDocumentsResponse, UploadSummary
from fe_bot.setup.upload.idempotency import (
    InMemoryIdempotencyCache,
    make_cache_key,
)

pytestmark = pytest.mark.unit


def _response(setup_job_id: str = "s1") -> UploadDocumentsResponse:
    return UploadDocumentsResponse(
        setup_job_id=setup_job_id,
        upload_batch_id="batch_001",
        summary=UploadSummary(
            files_total=1, files_uploaded=1, files_rejected=0, duplicates_detected=0
        ),
        uploaded=[],
        skipped_duplicates=[],
        errors=[],
        job_status=SetupJobStatus.FILES_UPLOADED,
        message="ok",
    )


class TestBasic:
    def test_get_missing_returns_none(self) -> None:
        cache = InMemoryIdempotencyCache()
        assert cache.get("any_key") is None

    def test_set_then_get_returns_response(self) -> None:
        cache = InMemoryIdempotencyCache()
        resp = _response()
        cache.set("k1", resp)
        cached = cache.get("k1")
        assert cached is not None
        assert cached.setup_job_id == "s1"

    def test_get_returns_deep_copy(self) -> None:
        cache = InMemoryIdempotencyCache()
        cache.set("k1", _response())
        first = cache.get("k1")
        assert first is not None
        # Мутация копии не должна повлиять на кеш.
        first.message = "mutated"
        second = cache.get("k1")
        assert second is not None and second.message == "ok"


class TestTTL:
    def test_expired_entry_returns_none_and_deletes(self) -> None:
        cache = InMemoryIdempotencyCache(ttl_seconds=0.05)
        cache.set("k1", _response())
        assert cache.size() == 1
        time.sleep(0.1)
        assert cache.get("k1") is None
        # Lazy cleanup: после доступа expired запись удалена.
        assert cache.size() == 0

    def test_unexpired_returns_response(self) -> None:
        cache = InMemoryIdempotencyCache(ttl_seconds=10.0)
        cache.set("k1", _response())
        # Сразу после set — ещё валиден.
        assert cache.get("k1") is not None


class TestCacheKey:
    def test_make_cache_key_combines_job_and_request(self) -> None:
        assert make_cache_key("setup_abc", "req_xyz") == "setup_abc:req_xyz"

    def test_different_jobs_same_request_id_different_keys(self) -> None:
        k1 = make_cache_key("setup_a", "req_x")
        k2 = make_cache_key("setup_b", "req_x")
        assert k1 != k2


class TestClear:
    def test_clear_removes_all(self) -> None:
        cache = InMemoryIdempotencyCache()
        cache.set("k1", _response())
        cache.set("k2", _response("s2"))
        assert cache.size() == 2
        cache.clear()
        assert cache.size() == 0
        assert cache.get("k1") is None


class TestSetReplaces:
    def test_set_replaces_existing_entry(self) -> None:
        cache = InMemoryIdempotencyCache()
        cache.set("k1", _response("s1"))
        cache.set("k1", _response("s2_overwritten"))
        cached = cache.get("k1")
        assert cached is not None and cached.setup_job_id == "s2_overwritten"
        # Используется now для silencing unused.
        _ = datetime.now(tz=UTC)
