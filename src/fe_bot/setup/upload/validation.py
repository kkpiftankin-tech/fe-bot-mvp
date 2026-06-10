"""Валидация загружаемых файлов (T-S01-012 + T-S02-004 filename safety).

Источник правил — SETUP-01 §18.1 + SETUP-02 §18.1.

T-S02-004: filename safety:
- запрет path traversal (`../`, `..\\`)
- запрет absolute paths (`/etc/passwd`)
- запрет null bytes и control characters
- длина ≤ 255 символов (POSIX limit)

Используется единый `UploadErrorCode` из `schemas/setup/upload_errors`
(вместо локального enum, удалённого в T-S02-004).
"""

from __future__ import annotations

from schemas.common.defaults import (
    MAX_BATCH_FILES_COUNT,
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_BATCH_SIZE_BYTES,
    SUPPORTED_CONTENT_TYPES,
)
from schemas.setup.upload_errors import UploadErrorCode

# Максимальная длина filename для POSIX-файловых систем.
MAX_FILENAME_LENGTH = 255

# Запрещённые подстроки в filename (T-S02-004).
_FORBIDDEN_FILENAME_PARTS: tuple[str, ...] = ("..", "/", "\\")


class UploadValidationError(ValueError):
    """Файл не прошёл валидацию."""

    def __init__(
        self,
        code: UploadErrorCode,
        message: str,
        *,
        filename: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.filename = filename
        self.details = details or {}
        super().__init__(message)


def _validate_filename_safety(filename: str) -> None:
    """Бросает UploadValidationError с INVALID_FILENAME / EMPTY_FILE если небезопасно."""
    if not filename or not filename.strip():
        raise UploadValidationError(
            UploadErrorCode.INVALID_FILENAME,
            "Filename is required",
            details={"reason": "empty"},
        )

    if len(filename) > MAX_FILENAME_LENGTH:
        raise UploadValidationError(
            UploadErrorCode.INVALID_FILENAME,
            f"Filename too long ({len(filename)} > {MAX_FILENAME_LENGTH})",
            filename=filename,
            details={
                "reason": "too_long",
                "length": len(filename),
                "limit": MAX_FILENAME_LENGTH,
            },
        )

    # Path traversal / absolute paths / separators.
    for part in _FORBIDDEN_FILENAME_PARTS:
        if part in filename:
            raise UploadValidationError(
                UploadErrorCode.INVALID_FILENAME,
                f"Filename contains forbidden sequence {part!r}",
                filename=filename,
                details={
                    "reason": "forbidden_sequence",
                    "sequence": part,
                },
            )

    # Null bytes и control characters (ASCII < 0x20, кроме разрешённого whitespace
    # tab — но и его не пропускаем чтобы избежать сюрпризов).
    for char in filename:
        if ord(char) < 0x20 or ord(char) == 0x7F:
            raise UploadValidationError(
                UploadErrorCode.INVALID_FILENAME,
                "Filename contains control character",
                filename=filename,
                details={
                    "reason": "control_character",
                    "char_code": ord(char),
                },
            )


def validate_file(
    *,
    filename: str | None,
    content_type: str | None,
    size_bytes: int,
) -> None:
    """Бросает UploadValidationError, если файл не подходит.

    Не читает данные — все проверки по metadata. Это позволяет отвергать
    плохие файлы до полной загрузки.
    """
    # Filename safety (T-S02-004).
    _validate_filename_safety(filename or "")

    # filename здесь гарантированно не-пустой и безопасный.
    assert filename is not None
    if size_bytes == 0:
        raise UploadValidationError(
            UploadErrorCode.EMPTY_FILE,
            f"Empty file: {filename!r}",
            filename=filename,
        )

    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise UploadValidationError(
            UploadErrorCode.FILE_TOO_LARGE,
            f"File {filename!r} ({size_bytes} bytes) exceeds limit {MAX_FILE_SIZE_BYTES}",
            filename=filename,
            details={"size_bytes": size_bytes, "limit": MAX_FILE_SIZE_BYTES},
        )

    if not content_type or content_type not in SUPPORTED_CONTENT_TYPES:
        raise UploadValidationError(
            UploadErrorCode.UNSUPPORTED_FILE_TYPE,
            f"Unsupported file type: {content_type!r} for {filename!r}",
            filename=filename,
            details={
                "content_type": content_type,
                "allowed": sorted(SUPPORTED_CONTENT_TYPES),
            },
        )


def check_filename_uniqueness(filenames: list[str]) -> None:
    """T-S02-006: filenames в одном batch должны быть уникальны.

    Если два файла в одном batch имеют одинаковое имя — отклоняем второй
    с error_code `INVALID_FILENAME`, потому что storage path будет
    конфликтным. Это **не** про cross-batch checksum-duplicate (тот случай
    обрабатывает DocumentUploadService через `find_by_checksum`).

    Raises:
        UploadValidationError: INVALID_FILENAME с details `duplicate_in_batch`.
    """
    seen: set[str] = set()
    for fname in filenames:
        if fname in seen:
            raise UploadValidationError(
                UploadErrorCode.INVALID_FILENAME,
                f"Filename {fname!r} appears more than once in batch",
                filename=fname,
                details={
                    "reason": "duplicate_in_batch",
                    "filename": fname,
                },
            )
        seen.add(fname)


def validate_batch_limits(
    *,
    files_count: int,
    total_size_bytes: int,
) -> None:
    """T-S02-005: batch-уровень ограничения.

    Эти проверки делаются **до** per-file validation в роутере, чтобы быстро
    отклонить заведомо неприемлемые batch-запросы и не тратить ресурсы на
    обработку отдельных файлов.

    Raises:
        UploadValidationError: BATCH_TOO_LARGE (по count или по size) или
            MISSING_FILES (если пусто).
    """
    if files_count == 0:
        raise UploadValidationError(
            UploadErrorCode.MISSING_FILES,
            "At least one file must be uploaded",
            details={"files_count": 0},
        )

    if files_count > MAX_BATCH_FILES_COUNT:
        raise UploadValidationError(
            UploadErrorCode.BATCH_TOO_LARGE,
            (
                f"Batch contains {files_count} files; "
                f"maximum is {MAX_BATCH_FILES_COUNT}"
            ),
            details={
                "reason": "too_many_files",
                "files_count": files_count,
                "limit": MAX_BATCH_FILES_COUNT,
            },
        )

    if total_size_bytes > MAX_TOTAL_BATCH_SIZE_BYTES:
        raise UploadValidationError(
            UploadErrorCode.BATCH_TOO_LARGE,
            (
                f"Batch total size {total_size_bytes} bytes exceeds limit "
                f"{MAX_TOTAL_BATCH_SIZE_BYTES} bytes"
            ),
            details={
                "reason": "total_size_exceeded",
                "total_size_bytes": total_size_bytes,
                "limit": MAX_TOTAL_BATCH_SIZE_BYTES,
            },
        )
