"""Тесты схем SourceDocument и UploadFile (T-S01-002)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.common.defaults import MAX_FILE_SIZE_BYTES
from schemas.setup.source_document import (
    DocumentKind,
    SourceDocument,
    SourceDocumentStatus,
)
from schemas.setup.upload_file import UploadFile

pytestmark = pytest.mark.unit


_VALID_CHECKSUM = "a" * 64


def _make_source(**overrides: object) -> SourceDocument:
    defaults: dict[str, object] = {
        "source_document_id": "src_001",
        "setup_job_id": "setup_001",
        "filename": "Situation.md",
        "content_type": "text/markdown",
        "storage_path": "s3://source-documents/setup_001/src_001/Situation.md",
        "size_bytes": 1024,
        "checksum": _VALID_CHECKSUM,
        "uploaded_by": "user_1",
        "uploaded_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return SourceDocument.model_validate(defaults)


def _make_upload(**overrides: object) -> UploadFile:
    defaults: dict[str, object] = {
        "file_name": "Situation.md",
        "content_type": "text/markdown",
        "size_bytes": 1024,
        "uploaded_by": "user_1",
        "setup_job_id": "setup_001",
    }
    defaults.update(overrides)
    return UploadFile.model_validate(defaults)


class TestUploadFile:
    def test_valid_upload(self) -> None:
        upload = _make_upload()
        assert upload.size_bytes == 1024

    def test_unsupported_content_type_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _make_upload(content_type="application/x-msdownload")
        assert "Unsupported content_type" in str(exc.value)

    def test_supported_types_all_pass(self) -> None:
        for ct in [
            "text/markdown",
            "text/plain",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
            "application/json",
        ]:
            assert _make_upload(content_type=ct).content_type == ct

    def test_empty_file_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _make_upload(size_bytes=0)
        assert "Empty file" in str(exc.value)

    def test_oversized_file_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _make_upload(size_bytes=MAX_FILE_SIZE_BYTES + 1)
        assert "exceeds limit" in str(exc.value)

    def test_at_size_limit_accepted(self) -> None:
        assert _make_upload(size_bytes=MAX_FILE_SIZE_BYTES).size_bytes == MAX_FILE_SIZE_BYTES

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            UploadFile.model_validate(
                {
                    "file_name": "f.md",
                    "content_type": "text/markdown",
                    "size_bytes": 1,
                    "uploaded_by": "u",
                    "setup_job_id": "s",
                    "unexpected": "x",
                }
            )


class TestSourceDocument:
    def test_valid_minimal(self) -> None:
        doc = _make_source()
        assert doc.status == SourceDocumentStatus.UPLOADED
        assert doc.parsed_at is None
        assert doc.document_kind is None

    def test_all_statuses(self) -> None:
        """SETUP-03 / T-S03-001: 20 статусов (7 legacy + 13 lifecycle)."""
        assert {s.value for s in SourceDocumentStatus} == {
            # Legacy (SETUP-01/02)
            "uploaded",
            "parsed",
            "converted",
            "failed",
            "failed_validation",
            "archived",
            "removed",
            # SETUP-03 lifecycle
            "registered",
            "metadata_extracted",
            "waiting_for_parsing",
            "parsing",
            "parse_failed",
            "sections_extracted",
            "rag_cards_generating",
            "rag_cards_generated",
            "review_required",
            "processing_failed",
            "ready_for_indexing",
            "published",
            "deprecated",
        }

    def test_setup_03_lifecycle_statuses_present(self) -> None:
        """T-S03-001: проверяем что все 13 новых статусов из §3 спека добавлены."""
        new_statuses = {
            SourceDocumentStatus.REGISTERED,
            SourceDocumentStatus.METADATA_EXTRACTED,
            SourceDocumentStatus.WAITING_FOR_PARSING,
            SourceDocumentStatus.PARSING,
            SourceDocumentStatus.PARSE_FAILED,
            SourceDocumentStatus.SECTIONS_EXTRACTED,
            SourceDocumentStatus.RAG_CARDS_GENERATING,
            SourceDocumentStatus.RAG_CARDS_GENERATED,
            SourceDocumentStatus.REVIEW_REQUIRED,
            SourceDocumentStatus.PROCESSING_FAILED,
            SourceDocumentStatus.READY_FOR_INDEXING,
            SourceDocumentStatus.PUBLISHED,
            SourceDocumentStatus.DEPRECATED,
        }
        assert len(new_statuses) == 13
        for s in new_statuses:
            assert s in SourceDocumentStatus

    def test_legacy_statuses_preserved(self) -> None:
        """T-S03-001: backward compat — старые статусы не удалены."""
        legacy = {
            SourceDocumentStatus.UPLOADED,
            SourceDocumentStatus.PARSED,
            SourceDocumentStatus.CONVERTED,
            SourceDocumentStatus.FAILED,
            SourceDocumentStatus.FAILED_VALIDATION,
            SourceDocumentStatus.ARCHIVED,
            SourceDocumentStatus.REMOVED,
        }
        assert len(legacy) == 7

    def test_checksum_must_be_sha256_64hex(self) -> None:
        with pytest.raises(ValidationError):
            _make_source(checksum="short")
        with pytest.raises(ValidationError):
            _make_source(checksum="g" * 64)  # not hex

    def test_checksum_accepts_prefix_and_strips(self) -> None:
        doc = _make_source(checksum=f"sha256:{_VALID_CHECKSUM}")
        assert doc.checksum == _VALID_CHECKSUM  # prefix stripped

    def test_size_bytes_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            _make_source(size_bytes=0)

    def test_size_bytes_within_limit(self) -> None:
        with pytest.raises(ValidationError):
            _make_source(size_bytes=MAX_FILE_SIZE_BYTES + 1)

    def test_unsupported_content_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_source(content_type="application/x-msdownload")

    def test_document_kind_optional(self) -> None:
        doc = _make_source(document_kind=DocumentKind.ANALYTICS)
        assert doc.document_kind == DocumentKind.ANALYTICS

    def test_round_trip_json(self) -> None:
        doc = _make_source(
            status=SourceDocumentStatus.PARSED,
            parsed_at=datetime(2026, 5, 19, 10, 5, tzinfo=UTC),
            document_kind=DocumentKind.SCHEMA,
        )
        restored = SourceDocument.model_validate_json(doc.model_dump_json())
        assert restored == doc

    def test_extra_fields_forbidden(self) -> None:
        payload = _make_source().model_dump()
        payload["unexpected"] = 1
        with pytest.raises(ValidationError):
            SourceDocument.model_validate(payload)
