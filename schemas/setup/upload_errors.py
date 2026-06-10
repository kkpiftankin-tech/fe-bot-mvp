"""Upload error codes + UploadFileError DTO (SETUP-02 / T-S02-002).

Стабильный машиночитаемый контракт ошибок upload-flow для frontend и audit.

**Контракт:** значения `UploadErrorCode` (string) являются частью API-контракта
и не могут меняться без bump'а DTO-версии. Тесты `test_upload_errors.py`
фиксируют каждое значение.

HTTP mapping (см. SETUP-02 §18):
    MISSING_FILES                → 400
    UNSUPPORTED_FILE_TYPE        → 415
    FILE_TOO_LARGE               → 413
    BATCH_TOO_LARGE              → 413
    EMPTY_FILE                   → 400
    INVALID_FILENAME             → 400
    DUPLICATE_FILE               → 200 (per-file в response.duplicates)
    SETUP_JOB_NOT_FOUND          → 404
    SETUP_JOB_NOT_UPLOADABLE     → 409
    INSUFFICIENT_PERMISSIONS     → 403
    OBJECT_STORAGE_*             → 500
    SOURCE_REGISTRY_*            → 500
    CHECKSUM_*                   → 500
    UPLOAD_STREAM_INTERRUPTED    → 500
    INTERNAL_UPLOAD_ERROR        → 500
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UploadErrorCode(StrEnum):
    # Validation errors (4xx)
    MISSING_FILES = "MISSING_FILES"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    BATCH_TOO_LARGE = "BATCH_TOO_LARGE"
    EMPTY_FILE = "EMPTY_FILE"
    INVALID_FILENAME = "INVALID_FILENAME"

    # Business-level (per-file rejection)
    DUPLICATE_FILE = "DUPLICATE_FILE"

    # Access / state errors
    SETUP_JOB_NOT_FOUND = "SETUP_JOB_NOT_FOUND"
    SETUP_JOB_NOT_UPLOADABLE = "SETUP_JOB_NOT_UPLOADABLE"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # System errors (5xx)
    OBJECT_STORAGE_UNAVAILABLE = "OBJECT_STORAGE_UNAVAILABLE"
    OBJECT_STORAGE_WRITE_FAILED = "OBJECT_STORAGE_WRITE_FAILED"
    SOURCE_REGISTRY_UNAVAILABLE = "SOURCE_REGISTRY_UNAVAILABLE"
    CHECKSUM_CALCULATION_FAILED = "CHECKSUM_CALCULATION_FAILED"
    UPLOAD_STREAM_INTERRUPTED = "UPLOAD_STREAM_INTERRUPTED"
    INTERNAL_UPLOAD_ERROR = "INTERNAL_UPLOAD_ERROR"


# HTTP code, который должен вернуть endpoint при батч-фейле этого типа.
# Per-file ошибки внутри 200 response: смотри SETUP-02 §16.1.
ERROR_CODE_HTTP_STATUS: dict[UploadErrorCode, int] = {
    UploadErrorCode.MISSING_FILES: 400,
    UploadErrorCode.UNSUPPORTED_FILE_TYPE: 415,
    UploadErrorCode.FILE_TOO_LARGE: 413,
    UploadErrorCode.BATCH_TOO_LARGE: 413,
    UploadErrorCode.EMPTY_FILE: 400,
    UploadErrorCode.INVALID_FILENAME: 400,
    UploadErrorCode.DUPLICATE_FILE: 200,  # не fail-весь-batch
    UploadErrorCode.SETUP_JOB_NOT_FOUND: 404,
    UploadErrorCode.SETUP_JOB_NOT_UPLOADABLE: 409,
    UploadErrorCode.INSUFFICIENT_PERMISSIONS: 403,
    UploadErrorCode.OBJECT_STORAGE_UNAVAILABLE: 500,
    UploadErrorCode.OBJECT_STORAGE_WRITE_FAILED: 500,
    UploadErrorCode.SOURCE_REGISTRY_UNAVAILABLE: 500,
    UploadErrorCode.CHECKSUM_CALCULATION_FAILED: 500,
    UploadErrorCode.UPLOAD_STREAM_INTERRUPTED: 500,
    UploadErrorCode.INTERNAL_UPLOAD_ERROR: 500,
}


class UploadFileError(BaseModel):
    """Структурированная ошибка per-file для UploadDocumentsResponse.errors."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(..., min_length=1, max_length=255)
    error_code: UploadErrorCode
    message: str = Field(..., min_length=1, max_length=4000)
    details: dict[str, Any] = Field(default_factory=dict)


def http_status_for(error_code: UploadErrorCode) -> int:
    """Возвращает HTTP-код для batch-уровня этой ошибки."""
    return ERROR_CODE_HTTP_STATUS[error_code]
