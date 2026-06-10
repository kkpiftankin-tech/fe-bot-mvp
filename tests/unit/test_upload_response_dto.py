"""Тесты UploadDocumentsResponse v2 + UploadSummary (T-S02-003)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.rag_setup_job import SetupJobStatus
from schemas.setup.upload_errors import UploadErrorCode, UploadFileError

from fe_bot.api.setup.dto import (
    SourceDocumentResponse,
    UploadDocumentsResponse,
    UploadSummary,
)

pytestmark = pytest.mark.unit


def _doc(filename: str = "x.md") -> SourceDocumentResponse:
    return SourceDocumentResponse(
        source_document_id="src_001",
        setup_job_id="setup_001",
        filename=filename,
        content_type="text/markdown",
        size_bytes=100,
        checksum="abc",
        status="uploaded",
        uploaded_by="u1",
        uploaded_at=datetime(2026, 6, 10, tzinfo=UTC),
    )


def _err(
    filename: str = "bad.exe",
    code: UploadErrorCode = UploadErrorCode.UNSUPPORTED_FILE_TYPE,
) -> UploadFileError:
    return UploadFileError(filename=filename, error_code=code, message="m")


class TestUploadSummary:
    def test_valid_summary(self) -> None:
        s = UploadSummary(
            files_total=5,
            files_uploaded=3,
            files_rejected=1,
            duplicates_detected=1,
        )
        assert s.files_total == 5

    def test_negative_counter_rejected(self) -> None:
        with pytest.raises(ValueError):
            UploadSummary(
                files_total=5,
                files_uploaded=-1,
                files_rejected=0,
                duplicates_detected=0,
            )

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="extra"):
            UploadSummary.model_validate(
                {
                    "files_total": 1,
                    "files_uploaded": 1,
                    "files_rejected": 0,
                    "duplicates_detected": 0,
                    "rogue": "x",
                }
            )


class TestUploadDocumentsResponseV2:
    def test_v1_shape_still_works(self) -> None:
        """Backward compat: v1-клиенты конструируют без summary/errors/batch_id."""
        resp = UploadDocumentsResponse(
            setup_job_id="setup_001",
            uploaded=[_doc()],
            skipped_duplicates=[],
            job_status=SetupJobStatus.FILES_UPLOADED,
        )
        assert resp.upload_batch_id is None
        assert resp.summary is None
        assert resp.errors == []

    def test_v2_full_shape(self) -> None:
        resp = UploadDocumentsResponse(
            setup_job_id="setup_001",
            upload_batch_id="batch_001",
            summary=UploadSummary(
                files_total=3,
                files_uploaded=1,
                files_rejected=1,
                duplicates_detected=1,
            ),
            uploaded=[_doc("good.md")],
            skipped_duplicates=[_doc("dup.md")],
            errors=[_err("bad.exe", UploadErrorCode.UNSUPPORTED_FILE_TYPE)],
            job_status=SetupJobStatus.FILES_UPLOADED,
            message="Uploaded 1, 1 duplicate, 1 rejected",
        )
        assert resp.upload_batch_id == "batch_001"
        assert resp.summary is not None
        assert resp.summary.files_total == 3
        assert resp.errors[0].error_code == UploadErrorCode.UNSUPPORTED_FILE_TYPE

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="extra"):
            UploadDocumentsResponse.model_validate(
                {
                    "setup_job_id": "x",
                    "uploaded": [],
                    "skipped_duplicates": [],
                    "job_status": "draft",
                    "rogue": "boom",
                }
            )

    def test_serializes_errors_with_error_code_string(self) -> None:
        resp = UploadDocumentsResponse(
            setup_job_id="x",
            uploaded=[],
            skipped_duplicates=[],
            errors=[_err("a.exe", UploadErrorCode.UNSUPPORTED_FILE_TYPE)],
            job_status=SetupJobStatus.DRAFT,
        )
        payload = resp.model_dump(mode="json")
        assert payload["errors"][0]["error_code"] == "UNSUPPORTED_FILE_TYPE"

    def test_summary_consistency_with_lists(self) -> None:
        """Document-уровень: caller обязан держать summary в синхроне со списками.

        DTO не делает кросс-валидацию (summary считается на backend в Document
        Upload Service); этот тест документирует ожидаемое использование.
        """
        summary = UploadSummary(
            files_total=2,
            files_uploaded=1,
            files_rejected=1,
            duplicates_detected=0,
        )
        resp = UploadDocumentsResponse(
            setup_job_id="x",
            upload_batch_id="b",
            summary=summary,
            uploaded=[_doc()],
            skipped_duplicates=[],
            errors=[_err()],
            job_status=SetupJobStatus.FILES_UPLOADED,
        )
        # Caller-level consistency check (не enforced DTO).
        assert (
            resp.summary is not None
            and resp.summary.files_uploaded == len(resp.uploaded)
        )
        assert resp.summary.files_rejected == len(resp.errors)
        assert resp.summary.duplicates_detected == len(resp.skipped_duplicates)
