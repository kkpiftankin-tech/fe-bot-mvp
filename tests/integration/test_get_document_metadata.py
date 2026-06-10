"""Integration: GET /api/v1/setup/{id}/documents/{doc_id} (T-S02-015)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Get KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


def _upload_one(
    client: TestClient,
    setup_job_id: str,
    headers: dict[str, str],
) -> str:
    resp = client.post(
        f"/api/v1/setup/{setup_job_id}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    )
    return resp.json()["uploaded"][0]["source_document_id"]


class TestGetDocumentMetadata:
    def test_returns_full_metadata(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_document_id"] == doc_id
        assert body["filename"] == "doc.md"
        assert body["content_type"] == "text/markdown"
        assert body["checksum"]  # SHA-256 присутствует
        assert body["status"] == "uploaded"

    def test_storage_path_masked_for_non_admin(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers
        )
        # Обычный user (нет kb.publish) → storage_path = null
        assert resp.json()["storage_path"] is None

    def test_storage_path_visible_for_admin(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/documents/{doc_id}", headers=admin_headers
        )
        assert resp.json()["storage_path"] is not None


class TestGetDocumentErrors:
    def test_unknown_document_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/documents/src_nope", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_cross_job_document_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid1 = _create_job(client, auth_headers)
        sid2 = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid1, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid2}/documents/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_unknown_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get(
            "/api/v1/setup/unknown_xxxx/documents/src_xx", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_other_user_cannot_access(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload_one(client, sid, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/documents/{doc_id}",
            headers={"X-User-Id": "u2", "X-Roles": "user"},
        )
        assert resp.status_code == 403
