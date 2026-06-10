"""Тесты batch-уровня ограничений upload (T-S02-005)."""

from __future__ import annotations

import pytest
from schemas.common.defaults import (
    MAX_BATCH_FILES_COUNT,
    MAX_TOTAL_BATCH_SIZE_BYTES,
)
from schemas.setup.upload_errors import UploadErrorCode

from fe_bot.setup.upload.validation import (
    UploadValidationError,
    validate_batch_limits,
)

pytestmark = pytest.mark.unit


class TestBatchEmpty:
    def test_zero_files_raises_missing_files(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_batch_limits(files_count=0, total_size_bytes=0)
        assert exc.value.code == UploadErrorCode.MISSING_FILES


class TestBatchCountLimit:
    def test_at_count_limit_ok(self) -> None:
        validate_batch_limits(
            files_count=MAX_BATCH_FILES_COUNT, total_size_bytes=100
        )

    def test_above_count_limit_raises_batch_too_large(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_batch_limits(
                files_count=MAX_BATCH_FILES_COUNT + 1, total_size_bytes=100
            )
        assert exc.value.code == UploadErrorCode.BATCH_TOO_LARGE
        assert exc.value.details["reason"] == "too_many_files"
        assert exc.value.details["files_count"] == MAX_BATCH_FILES_COUNT + 1
        assert exc.value.details["limit"] == MAX_BATCH_FILES_COUNT


class TestBatchSizeLimit:
    def test_at_size_limit_ok(self) -> None:
        validate_batch_limits(
            files_count=1, total_size_bytes=MAX_TOTAL_BATCH_SIZE_BYTES
        )

    def test_above_size_limit_raises_batch_too_large(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_batch_limits(
                files_count=1, total_size_bytes=MAX_TOTAL_BATCH_SIZE_BYTES + 1
            )
        assert exc.value.code == UploadErrorCode.BATCH_TOO_LARGE
        assert exc.value.details["reason"] == "total_size_exceeded"
        assert (
            exc.value.details["total_size_bytes"]
            == MAX_TOTAL_BATCH_SIZE_BYTES + 1
        )

    def test_count_check_comes_before_size_check(self) -> None:
        """Если batch и слишком большой по count, и по size — приоритет у count."""
        with pytest.raises(UploadValidationError) as exc:
            validate_batch_limits(
                files_count=MAX_BATCH_FILES_COUNT + 1,
                total_size_bytes=MAX_TOTAL_BATCH_SIZE_BYTES + 1,
            )
        assert exc.value.details["reason"] == "too_many_files"


class TestNormalBatch:
    def test_typical_small_batch_ok(self) -> None:
        validate_batch_limits(files_count=3, total_size_bytes=10_000)
