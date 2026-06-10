"""Unit: structured logging для upload-flow (T-S02-013).

Проверяет, что DocumentUploadService логирует с правильными extra-полями,
которые JSONFormatter из S8 материализует в structured JSON.
"""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest
from schemas.setup.rag_setup_job import RAGSetupJob, SetupJobStatus

from fe_bot.observability.logging_config import JSONFormatter
from fe_bot.setup.events import EventBus
from fe_bot.setup.repository import InMemoryJobRepository
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.setup.upload.service import DocumentUploadService
from fe_bot.storage.artifact_service import InMemoryArtifactStorage

pytestmark = pytest.mark.unit


@pytest.fixture
def captured_logs() -> tuple[StringIO, DocumentUploadService, str]:
    """Возвращает (buffer, service, setup_job_id)."""
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JSONFormatter())
    svc_logger = logging.getLogger("fe_bot.setup.upload.service")
    for h in list(svc_logger.handlers):
        svc_logger.removeHandler(h)
    svc_logger.addHandler(handler)
    svc_logger.setLevel(logging.DEBUG)
    svc_logger.propagate = False

    repo = InMemoryJobRepository()
    bus = EventBus()
    storage = InMemoryArtifactStorage()
    registry = InMemorySourceRegistry()
    job = RAGSetupJob(
        setup_job_id="setup_log_test",
        user_id="u1",
        project_name="Log Test",
        status=SetupJobStatus.DRAFT,
        progress_percent=0.0,
        error_count=0,
        warning_count=0,
    )
    repo.save(job)
    svc = DocumentUploadService(
        job_repository=repo,
        source_registry=registry,
        artifact_storage=storage,
        event_bus=bus,
        # audit/metrics не подключены — тест только про logging.
    )
    return buf, svc, "setup_log_test"


def _parse_log_lines(buf: StringIO) -> list[dict]:
    text = buf.getvalue().strip()
    if not text:
        return []
    return [json.loads(line) for line in text.split("\n") if line.strip()]


class TestSuccessfulUploadLogs:
    def test_logs_started_and_completed(
        self,
        captured_logs: tuple[StringIO, DocumentUploadService, str],
    ) -> None:
        buf, svc, sid = captured_logs
        svc.upload(
            setup_job_id=sid,
            filename="doc.md",
            content_type="text/markdown",
            data=b"content",
            uploaded_by="u1",
        )
        records = _parse_log_lines(buf)
        messages = [r["message"] for r in records]
        assert "upload.started" in messages
        assert "upload.completed" in messages

    def test_started_log_has_structured_fields(
        self,
        captured_logs: tuple[StringIO, DocumentUploadService, str],
    ) -> None:
        buf, svc, sid = captured_logs
        svc.upload(
            setup_job_id=sid,
            filename="doc.md",
            content_type="text/markdown",
            data=b"hello",
            uploaded_by="u1",
        )
        records = _parse_log_lines(buf)
        started = next(r for r in records if r["message"] == "upload.started")
        assert started["setup_job_id"] == sid
        assert started["doc_filename"] == "doc.md"
        assert started["size_bytes"] == 5
        assert started["duplicate_strategy"] == "skip"
        assert started["level"] == "INFO"

    def test_completed_log_has_source_document_id(
        self,
        captured_logs: tuple[StringIO, DocumentUploadService, str],
    ) -> None:
        buf, svc, sid = captured_logs
        result = svc.upload(
            setup_job_id=sid,
            filename="doc.md",
            content_type="text/markdown",
            data=b"x",
            uploaded_by="u1",
        )
        records = _parse_log_lines(buf)
        completed = next(r for r in records if r["message"] == "upload.completed")
        assert completed["source_document_id"] == result.document.source_document_id
        assert "checksum" in completed  # truncated


class TestRejectedLog:
    def test_validation_failure_logs_warning(
        self,
        captured_logs: tuple[StringIO, DocumentUploadService, str],
    ) -> None:
        buf, svc, sid = captured_logs
        from fe_bot.setup.upload.validation import UploadValidationError

        with pytest.raises(UploadValidationError):
            svc.upload(
                setup_job_id=sid,
                filename="bad.exe",
                content_type="application/x-msdownload",
                data=b"x",
                uploaded_by="u1",
            )
        records = _parse_log_lines(buf)
        rejected = next(r for r in records if r["message"] == "upload.rejected")
        assert rejected["level"] == "WARNING"
        assert rejected["error_code"] == "UNSUPPORTED_FILE_TYPE"
        assert rejected["doc_filename"] == "bad.exe"
