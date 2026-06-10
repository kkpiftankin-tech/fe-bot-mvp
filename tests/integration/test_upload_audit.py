"""Integration: AuditEvents для upload-flow (T-S02-011)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fe_bot.audit.service import AuditAction, AuditOutcome

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Audit KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


def _audit_log(app):
    from fe_bot.api.dependencies import get_audit_log

    return app.dependency_overrides[get_audit_log]()


class TestDocumentUploadedAudit:
    def test_successful_upload_records_document_uploaded(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("doc.md", b"content", "text/markdown")},
            headers=auth_headers,
        )
        events = _audit_log(app_with_clean_state).list_for_job(sid)
        uploaded = [e for e in events if e.action == AuditAction.DOCUMENT_UPLOADED]
        assert len(uploaded) == 1
        assert uploaded[0].payload["filename"] == "doc.md"
        assert uploaded[0].payload["size_bytes"] == len(b"content")
        assert uploaded[0].outcome == AuditOutcome.SUCCESS

    def test_uploaded_event_has_actor_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        events = _audit_log(app_with_clean_state).list_for_job(sid)
        uploaded = next(
            e for e in events if e.action == AuditAction.DOCUMENT_UPLOADED
        )
        assert uploaded.actor_id == "u1"


class TestDocumentRejectedAudit:
    def test_rejected_file_records_document_rejected(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("bad.exe", b"x", "application/x-msdownload")},
            headers=auth_headers,
        )
        events = _audit_log(app_with_clean_state).list_for_job(sid)
        rejected = [e for e in events if e.action == AuditAction.DOCUMENT_REJECTED]
        assert len(rejected) == 1
        assert rejected[0].outcome == AuditOutcome.FAILURE
        assert rejected[0].payload["error_code"] == "UNSUPPORTED_FILE_TYPE"
        assert rejected[0].payload["filename"] == "bad.exe"


class TestDocumentDuplicateSkippedAudit:
    def test_duplicate_records_document_duplicate_skipped(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"content", "text/markdown")},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"content", "text/markdown")},
            headers=auth_headers,
        )
        events = _audit_log(app_with_clean_state).list_for_job(sid)
        dup = [e for e in events if e.action == AuditAction.DOCUMENT_DUPLICATE_SKIPPED]
        assert len(dup) == 1
        assert "existing_doc_id" in dup[0].payload


class TestBatchCompletedAudit:
    def test_batch_records_completion_event(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        events = _audit_log(app_with_clean_state).list_for_job(sid)
        batch_events = [e for e in events if e.action == AuditAction.BATCH_COMPLETED]
        assert len(batch_events) == 1
        payload = batch_events[0].payload
        assert payload["files_total"] == 1
        assert payload["files_uploaded"] == 1
        assert payload["terminal_status"] == "completed"

    def test_partial_batch_audit_shows_partial_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        files = [
            ("files", ("good.md", b"ok", "text/markdown")),
            ("files", ("bad.exe", b"bad", "application/x-msdownload")),
        ]
        client.post(
            f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers
        )
        events = _audit_log(app_with_clean_state).list_for_job(sid)
        batch = next(
            e for e in events if e.action == AuditAction.BATCH_COMPLETED
        )
        assert batch.payload["terminal_status"] == "partially_completed"
        assert batch.payload["files_rejected"] == 1
        # Должны быть и individual document.uploaded и document.rejected events.
        actions = {e.action for e in events}
        assert AuditAction.DOCUMENT_UPLOADED in actions
        assert AuditAction.DOCUMENT_REJECTED in actions
