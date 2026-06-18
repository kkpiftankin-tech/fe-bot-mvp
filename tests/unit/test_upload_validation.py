"""Тесты валидации загружаемых файлов (T-S01-012 + T-S02-004 filename safety)."""

from __future__ import annotations

import pytest
from schemas.common.defaults import MAX_FILE_SIZE_BYTES
from schemas.setup.upload_errors import UploadErrorCode

from fe_bot.setup.upload.validation import (
    MAX_FILENAME_LENGTH,
    UploadValidationError,
    validate_file,
)

pytestmark = pytest.mark.unit


class TestValidateFile:
    def test_valid_markdown(self) -> None:
        validate_file(filename="doc.md", content_type="text/markdown", size_bytes=100)

    def test_missing_filename(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(filename=None, content_type="text/markdown", size_bytes=10)
        # T-S02-004: MISSING_FILENAME → INVALID_FILENAME (с details.reason="empty")
        assert exc.value.code == UploadErrorCode.INVALID_FILENAME
        assert exc.value.details["reason"] == "empty"

    def test_whitespace_filename(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(filename="   ", content_type="text/markdown", size_bytes=10)
        assert exc.value.code == UploadErrorCode.INVALID_FILENAME
        assert exc.value.details["reason"] == "empty"

    def test_empty_file(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(filename="empty.md", content_type="text/markdown", size_bytes=0)
        assert exc.value.code == UploadErrorCode.EMPTY_FILE
        assert exc.value.filename == "empty.md"

    def test_oversized_file(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(
                filename="big.md",
                content_type="text/markdown",
                size_bytes=MAX_FILE_SIZE_BYTES + 1,
            )
        assert exc.value.code == UploadErrorCode.FILE_TOO_LARGE
        assert exc.value.details["limit"] == MAX_FILE_SIZE_BYTES

    def test_at_size_limit_accepted(self) -> None:
        validate_file(
            filename="ok.md",
            content_type="text/markdown",
            size_bytes=MAX_FILE_SIZE_BYTES,
        )

    def test_unsupported_content_type(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(
                filename="bad.exe",
                content_type="application/x-msdownload",
                size_bytes=100,
            )
        assert exc.value.code == UploadErrorCode.UNSUPPORTED_FILE_TYPE
        assert "application/x-msdownload" in exc.value.details["content_type"]  # type: ignore[operator]
        assert "text/markdown" in exc.value.details["allowed"]  # type: ignore[operator]

    def test_missing_content_type(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(filename="doc", content_type=None, size_bytes=100)
        assert exc.value.code == UploadErrorCode.UNSUPPORTED_FILE_TYPE

    @pytest.mark.parametrize(
        "content_type",
        [
            "text/markdown",
            "text/plain",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
            "application/json",
        ],
    )
    def test_all_supported_types(self, content_type: str) -> None:
        validate_file(
            filename=f"doc.{content_type.split('/')[-1]}",
            content_type=content_type,
            size_bytes=100,
        )


class TestFilenameSafety:
    """T-S02-004: проверки против path traversal / control chars / длины."""

    @pytest.mark.parametrize(
        "bad_filename,expected_reason",
        [
            ("../etc/passwd", "forbidden_sequence"),
            ("..\\windows\\system32\\config", "forbidden_sequence"),
            ("/etc/hosts", "forbidden_sequence"),
            ("file/with/slashes.md", "forbidden_sequence"),
            ("file\\with\\backslash.md", "forbidden_sequence"),
            ("..", "forbidden_sequence"),
            ("file..name.md", "forbidden_sequence"),  # любой `..` запрещён
        ],
    )
    def test_path_traversal_rejected(self, bad_filename: str, expected_reason: str) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(
                filename=bad_filename,
                content_type="text/markdown",
                size_bytes=100,
            )
        assert exc.value.code == UploadErrorCode.INVALID_FILENAME
        assert exc.value.details["reason"] == expected_reason

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(UploadValidationError) as exc:
            validate_file(
                filename="bad\x00name.md",
                content_type="text/markdown",
                size_bytes=100,
            )
        assert exc.value.code == UploadErrorCode.INVALID_FILENAME
        assert exc.value.details["reason"] == "control_character"
        assert exc.value.details["char_code"] == 0

    def test_control_character_rejected(self) -> None:
        # \x07 = BEL
        with pytest.raises(UploadValidationError) as exc:
            validate_file(
                filename="bad\x07name.md",
                content_type="text/markdown",
                size_bytes=100,
            )
        assert exc.value.code == UploadErrorCode.INVALID_FILENAME
        assert exc.value.details["char_code"] == 7

    def test_filename_too_long(self) -> None:
        long_name = "a" * (MAX_FILENAME_LENGTH + 1) + ".md"
        with pytest.raises(UploadValidationError) as exc:
            validate_file(
                filename=long_name,
                content_type="text/markdown",
                size_bytes=100,
            )
        assert exc.value.code == UploadErrorCode.INVALID_FILENAME
        assert exc.value.details["reason"] == "too_long"
        assert exc.value.details["length"] == len(long_name)

    def test_filename_at_length_limit_ok(self) -> None:
        # 252 chars + ".md" = 255 chars
        ok_name = "a" * 252 + ".md"
        validate_file(filename=ok_name, content_type="text/markdown", size_bytes=100)

    @pytest.mark.parametrize(
        "safe_filename",
        [
            "valid name.md",
            "файл-с-кириллицей.txt",
            "data-2026-06-10.csv",
            "Доклад_v1.docx",
            "report (final).pdf",
        ],
    )
    def test_safe_filenames_accepted(self, safe_filename: str) -> None:
        # Подбираем подходящий content_type под расширение.
        content_types = {
            "md": "text/markdown",
            "txt": "text/plain",
            "csv": "text/csv",
            "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "pdf": "application/pdf",
        }
        ext = safe_filename.rsplit(".", 1)[-1].lower()
        validate_file(
            filename=safe_filename,
            content_type=content_types[ext],
            size_bytes=100,
        )
