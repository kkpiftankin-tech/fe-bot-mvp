"""Integration: Upload → SourceLifecycle integration (T-S03-019).

После успешного upload автоматически:
- update_status(UPLOADED→REGISTERED)
- append_processing_log(step=UPLOAD, level=INFO)

Idempotent через event_id — повторный upload (через идемпотентность batch)
не создаёт лишние записи.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.processing_log import ProcessingLogStep
from schemas.setup.source_document import SourceDocumentStatus

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Flow KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(
    client: TestClient,
    sid: str,
    headers: dict[str, str],
    filename: str = "doc.md",
    content: bytes = b"content",
) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": (filename, content, "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


def _history_repo(app):
    from fe_bot.api.dependencies import get_status_history_repo

    return app.dependency_overrides[get_status_history_repo]()


def _log_repo(app):
    from fe_bot.api.dependencies import get_processing_log_repo

    return app.dependency_overrides[get_processing_log_repo]()


def _registry(app):
    from fe_bot.api.dependencies import get_source_registry

    return app.dependency_overrides[get_source_registry]()


class TestUploadAutoRegistration:
    def test_status_is_registered_after_upload(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        doc = _registry(app_with_clean_state).get(doc_id)
        assert doc.status == SourceDocumentStatus.REGISTERED

    def test_history_has_uploaded_to_registered_entry(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        entries = _history_repo(app_with_clean_state).list_for_document(doc_id)
        assert len(entries) == 1
        assert entries[0].old_status == SourceDocumentStatus.UPLOADED
        assert entries[0].new_status == SourceDocumentStatus.REGISTERED
        assert entries[0].changed_by_id == "document-upload-service"

    def test_processing_log_has_upload_entry(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        logs = _log_repo(app_with_clean_state).list_for_document(
            doc_id, step=ProcessingLogStep.UPLOAD
        )
        assert len(logs) == 1
        assert "Document uploaded" in logs[0].message
        assert logs[0].payload["size_bytes"] > 0


class TestUploadIdempotency:
    def test_duplicate_skip_does_not_double_register(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Duplicate upload (skip) НЕ создаёт повторных history/log entries.

        Существующий документ — пропускаем; для duplicate'а lifecycle hooks
        не вызываются (только для нового документа).
        """
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers, content=b"X")
        # Second upload same content → duplicate (skip).
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("doc2.md", b"X", "text/markdown")},
            headers=auth_headers,
        ).json()
        assert resp["summary"]["duplicates_detected"] == 1
        # Только одна запись в history для первого upload.
        entries = _history_repo(app_with_clean_state).list_for_document(doc_id)
        assert len(entries) == 1
        # Processing log — тоже одна запись.
        logs = _log_repo(app_with_clean_state).list_for_document(
            doc_id, step=ProcessingLogStep.UPLOAD
        )
        assert len(logs) == 1
