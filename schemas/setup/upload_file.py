"""UploadFileDTO (DTO-08) — request на загрузку файла от frontend к API.

DTO транзитен (request/response, не хранится). Бинарь идёт в Object Storage,
metadata — в SourceDocumentDTO.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-08.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.common.defaults import MAX_FILE_SIZE_BYTES, SUPPORTED_CONTENT_TYPES


class UploadFile(BaseModel):
    """Метаданные загружаемого файла (без бинарного потока).

    Бинарь передаётся отдельно (multipart form-data); эта схема описывает
    структуру JSON-частей запроса.
    """

    model_config = ConfigDict(extra="forbid")

    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1)
    size_bytes: int = Field(..., ge=0)
    user_tags: list[str] = Field(default_factory=list)
    description: str | None = Field(None, max_length=2000)
    uploaded_by: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)

    @field_validator("content_type")
    @classmethod
    def _content_type_supported(cls, v: str) -> str:
        if v not in SUPPORTED_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported content_type: {v!r}. Allowed: {sorted(SUPPORTED_CONTENT_TYPES)}"
            )
        return v

    @field_validator("size_bytes")
    @classmethod
    def _size_within_limit(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Empty file (size_bytes == 0) is not allowed")
        if v > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size {v} bytes exceeds limit {MAX_FILE_SIZE_BYTES} bytes")
        return v
