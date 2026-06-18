"""Тесты UploadErrorCode + UploadFileError (T-S02-002)."""

from __future__ import annotations

import pytest
from schemas.setup.upload_errors import (
    ERROR_CODE_HTTP_STATUS,
    UploadErrorCode,
    UploadFileError,
    http_status_for,
)

pytestmark = pytest.mark.unit


class TestErrorCodeContract:
    """Каждое значение enum — часть публичного контракта API.

    Если эти тесты падают — это **breaking change**, требующий bump'а DTO-версии.
    """

    @pytest.mark.parametrize(
        "code,expected_value",
        [
            (UploadErrorCode.MISSING_FILES, "MISSING_FILES"),
            (UploadErrorCode.UNSUPPORTED_FILE_TYPE, "UNSUPPORTED_FILE_TYPE"),
            (UploadErrorCode.FILE_TOO_LARGE, "FILE_TOO_LARGE"),
            (UploadErrorCode.BATCH_TOO_LARGE, "BATCH_TOO_LARGE"),
            (UploadErrorCode.EMPTY_FILE, "EMPTY_FILE"),
            (UploadErrorCode.INVALID_FILENAME, "INVALID_FILENAME"),
            (UploadErrorCode.DUPLICATE_FILE, "DUPLICATE_FILE"),
            (UploadErrorCode.SETUP_JOB_NOT_FOUND, "SETUP_JOB_NOT_FOUND"),
            (
                UploadErrorCode.SETUP_JOB_NOT_UPLOADABLE,
                "SETUP_JOB_NOT_UPLOADABLE",
            ),
            (
                UploadErrorCode.INSUFFICIENT_PERMISSIONS,
                "INSUFFICIENT_PERMISSIONS",
            ),
            (
                UploadErrorCode.OBJECT_STORAGE_UNAVAILABLE,
                "OBJECT_STORAGE_UNAVAILABLE",
            ),
            (
                UploadErrorCode.OBJECT_STORAGE_WRITE_FAILED,
                "OBJECT_STORAGE_WRITE_FAILED",
            ),
            (
                UploadErrorCode.SOURCE_REGISTRY_UNAVAILABLE,
                "SOURCE_REGISTRY_UNAVAILABLE",
            ),
            (
                UploadErrorCode.CHECKSUM_CALCULATION_FAILED,
                "CHECKSUM_CALCULATION_FAILED",
            ),
            (
                UploadErrorCode.UPLOAD_STREAM_INTERRUPTED,
                "UPLOAD_STREAM_INTERRUPTED",
            ),
            (UploadErrorCode.INTERNAL_UPLOAD_ERROR, "INTERNAL_UPLOAD_ERROR"),
        ],
    )
    def test_string_value_stable(self, code: UploadErrorCode, expected_value: str) -> None:
        assert code.value == expected_value

    def test_all_codes_have_http_status_mapping(self) -> None:
        for code in UploadErrorCode:
            assert code in ERROR_CODE_HTTP_STATUS, f"{code.name} missing in ERROR_CODE_HTTP_STATUS"


class TestHttpStatusMapping:
    @pytest.mark.parametrize(
        "code,expected_status",
        [
            (UploadErrorCode.MISSING_FILES, 400),
            (UploadErrorCode.UNSUPPORTED_FILE_TYPE, 415),
            (UploadErrorCode.FILE_TOO_LARGE, 413),
            (UploadErrorCode.BATCH_TOO_LARGE, 413),
            (UploadErrorCode.SETUP_JOB_NOT_FOUND, 404),
            (UploadErrorCode.SETUP_JOB_NOT_UPLOADABLE, 409),
            (UploadErrorCode.INSUFFICIENT_PERMISSIONS, 403),
            (UploadErrorCode.DUPLICATE_FILE, 200),
            (UploadErrorCode.OBJECT_STORAGE_UNAVAILABLE, 500),
            (UploadErrorCode.INTERNAL_UPLOAD_ERROR, 500),
        ],
    )
    def test_http_status_for(self, code: UploadErrorCode, expected_status: int) -> None:
        assert http_status_for(code) == expected_status


class TestUploadFileError:
    def test_minimal_construction(self) -> None:
        err = UploadFileError(
            filename="bad.exe",
            error_code=UploadErrorCode.UNSUPPORTED_FILE_TYPE,
            message="Format not allowed",
        )
        assert err.filename == "bad.exe"
        assert err.error_code == UploadErrorCode.UNSUPPORTED_FILE_TYPE
        assert err.details == {}

    def test_with_details(self) -> None:
        err = UploadFileError(
            filename="data.exe",
            error_code=UploadErrorCode.UNSUPPORTED_FILE_TYPE,
            message="Формат не поддерживается",
            details={
                "allowed_extensions": ["md", "txt", "pdf"],
                "detected_extension": "exe",
            },
        )
        assert err.details["detected_extension"] == "exe"

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="extra"):
            UploadFileError.model_validate(
                {
                    "filename": "x.md",
                    "error_code": "MISSING_FILES",
                    "message": "m",
                    "rogue_field": "boom",
                }
            )

    def test_invalid_error_code_rejected(self) -> None:
        with pytest.raises(ValueError):
            UploadFileError.model_validate(
                {
                    "filename": "x.md",
                    "error_code": "NOT_A_REAL_CODE",
                    "message": "m",
                }
            )

    def test_serializes_to_json(self) -> None:
        err = UploadFileError(
            filename="x.md",
            error_code=UploadErrorCode.FILE_TOO_LARGE,
            message="too big",
            details={"size": 200_000_000, "limit": 100_000_000},
        )
        payload = err.model_dump(mode="json")
        # error_code сериализуется как string-значение enum.
        assert payload["error_code"] == "FILE_TOO_LARGE"
        assert payload["details"]["size"] == 200_000_000
