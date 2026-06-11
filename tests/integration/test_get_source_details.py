"""Integration: GET /sources/{id} (T-S03-013)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Details KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(
    client: TestClient,
    sid: str,
    headers: dict[str, str],
    filename: str = "doc.md",
) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": (filename, b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


class TestGetDetailsHappyPath:
    def test_returns_full_details(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["source_document_id"] == doc_id
        assert body["filename"] == "doc.md"
        assert body["content_type"] == "text/markdown"
        # T-S03-019: upload автоматически переводит в REGISTERED.
        assert body["status"] == "registered"
        assert len(body["checksum"]) == 64

    def test_includes_counters(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        ).json()
        assert body["counters"]["rag_cards_count"] == 0
        assert body["counters"]["parsed_sections_count"] == 0

    def test_user_metadata_empty_initially(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        ).json()
        assert body["user_metadata"] == {}


class TestStoragePathMasking:
    def test_storage_path_hidden_for_user(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        ).json()
        assert body["storage_path"] is None

    def test_storage_path_visible_for_admin(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=admin_headers
        ).json()
        assert body["storage_path"] is not None


class TestErrorPaths:
    def test_unknown_doc_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/src_nope", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_cross_job_doc_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid1 = _create_job(client, auth_headers)
        sid2 = _create_job(client, auth_headers)
        doc_id = _upload(client, sid1, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid2}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_other_user_403(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}",
            headers={"X-User-Id": "u2", "X-Roles": "user"},
        )
        assert resp.status_code == 403

    def test_removed_document_still_readable(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        client.delete(
            f"/api/v1/setup/{sid}/documents/{doc_id}", headers=auth_headers
        )
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"
