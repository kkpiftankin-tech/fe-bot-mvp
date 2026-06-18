"""Integration: DELETE /api/v1/setup/{id}/documents/{doc_id} (T-S02-014)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fe_bot.audit.service import AuditAction

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Delete KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


def _upload_one(
    client: TestClient,
    setup_job_id: str,
    headers: dict[str, str],
    content: bytes = b"content",
) -> str:
    resp = client.post(
        f"/api/v1/setup/{setup_job_id}/documents",
        files={"files": ("doc.md", content, "text/markdown")},
        headers=headers,
    )
    return resp.json()["uploaded"][0]["source_document_id"]


class TestDeleteHappyPath:
    def test_delete_returns_status_removed(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        resp = client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "removed"
        assert body["source_document_id"] == doc_id

    def test_get_after_delete_returns_removed_metadata(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        # GET single document после delete возвращает 200 + status=removed
        # (audit trail сохранён).
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"


class TestDeleteIdempotent:
    def test_repeated_delete_returns_same_response(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        first = client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        second = client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["status"] == "removed"


class TestDeleteReleasesDedup:
    def test_reupload_same_file_after_delete_succeeds(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """После DELETE тот же файл (same checksum) можно зарегистрировать снова."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers, content=b"X")
        client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        # Re-upload того же файла.
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("doc.md", b"X", "text/markdown")},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        # Не duplicate — освобождён ключ.
        assert body["summary"]["duplicates_detected"] == 0
        assert body["summary"]["files_uploaded"] == 1
        new_id = body["uploaded"][0]["source_document_id"]
        assert new_id != doc_id


class TestDeleteErrors:
    def test_unknown_document_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.delete(f"/api/v1/setup/{sid}/documents/src_nope", headers=auth_headers)
        assert resp.status_code == 404

    def test_cross_job_document_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid1 = _create_job(client, auth_headers)
        sid2 = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid1, auth_headers)
        # Пытаемся удалить из sid2.
        resp = client.delete(f"/api/v1/setup/{sid2}/documents/{doc_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_auditor_lacks_delete_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        resp = client.delete(
            f"/api/v1/setup/{sid}/documents/{doc_id}",
            headers={"X-User-Id": "auditor", "X-Roles": "auditor"},
        )
        assert resp.status_code == 403

    def test_unknown_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.delete(
            "/api/v1/setup/unknown_xxxx/documents/src_xx",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestDeleteAuditAndMetrics:
    def test_delete_records_document_removed_audit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_audit_log

        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        client.delete(
            f"/api/v1/setup/{sid}/documents/{doc_id}?reason=mistake",
            headers=auth_headers,
        )
        log = app_with_clean_state.dependency_overrides[get_audit_log]()
        events = log.list_for_job(sid)
        removed = [e for e in events if e.action == AuditAction.DOCUMENT_REMOVED]
        assert len(removed) == 1
        assert removed[0].payload["reason"] == "mistake"
        assert removed[0].target_id == doc_id

    def test_delete_increments_removed_counter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_metrics

        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        m = app_with_clean_state.dependency_overrides[get_metrics]()
        assert m.counter_value("upload_files_total", labels={"outcome": "removed"}) == 1.0

    def test_idempotent_delete_does_not_double_audit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_audit_log

        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        client.delete(f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers)
        log = app_with_clean_state.dependency_overrides[get_audit_log]()
        removed = [e for e in log.list_for_job(sid) if e.action == AuditAction.DOCUMENT_REMOVED]
        # Один event на первый delete; второй (idempotent) не повторяет audit.
        assert len(removed) == 1
