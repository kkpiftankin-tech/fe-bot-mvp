"""Integration: POST/GET /api/v1/setup/{id}/documents (T-S01-013, T-S01-015)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Naval KB"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["setup_job_id"]


class TestUploadDocuments:
    def test_upload_single_file_201(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("doc.md", b"# Hello\n", "text/markdown")},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["setup_job_id"] == sid
        assert len(body["uploaded"]) == 1
        assert body["uploaded"][0]["filename"] == "doc.md"
        assert body["uploaded"][0]["content_type"] == "text/markdown"
        assert body["uploaded"][0]["size_bytes"] == 8
        assert len(body["uploaded"][0]["checksum"]) == 64
        assert body["skipped_duplicates"] == []
        # Регулярный пользователь не видит storage_path
        assert body["uploaded"][0]["storage_path"] is None

    def test_upload_transitions_job_to_files_uploaded(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        assert resp.json()["job_status"] == "files_uploaded"

        status_resp = client.get(f"/api/v1/setup/{sid}", headers=auth_headers)
        assert status_resp.json()["status"] == "files_uploaded"
        assert status_resp.json()["source_documents_count"] == 1

    def test_upload_multiple_files(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files=[
                ("files", ("a.md", b"alpha", "text/markdown")),
                ("files", ("b.md", b"beta", "text/markdown")),
                ("files", ("c.json", b'{"x":1}', "application/json")),
            ],
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert len(resp.json()["uploaded"]) == 3

    def test_upload_duplicate_skipped_by_default(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        files = {"files": ("same.md", b"identical", "text/markdown")}
        first = client.post(
            f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers
        )
        assert len(first.json()["uploaded"]) == 1

        second = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("same.md", b"identical", "text/markdown")},
            headers=auth_headers,
        )
        body = second.json()
        assert second.status_code == 201
        assert body["uploaded"] == []
        assert len(body["skipped_duplicates"]) == 1
        # Same source_document_id returned
        assert (
            body["skipped_duplicates"][0]["source_document_id"]
            == first.json()["uploaded"][0]["source_document_id"]
        )

    def test_upload_rejects_unsupported_type(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # T-S02-006: per-file errors теперь идут в response.errors[], не 400.
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("bad.exe", b"binary", "application/x-msdownload")},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body["errors"]) == 1
        assert body["errors"][0]["error_code"] == "UNSUPPORTED_FILE_TYPE"
        assert body["summary"]["files_rejected"] == 1
        assert body["summary"]["files_uploaded"] == 0

    def test_upload_rejects_empty_file(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("empty.md", b"", "text/markdown")},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["errors"][0]["error_code"] == "EMPTY_FILE"

    def test_upload_to_unknown_job_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post(
            "/api/v1/setup/setup_nope/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_upload_other_user_job_403(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        other = {"X-User-Id": "u2", "X-Roles": "user"}
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=other,
        )
        assert resp.status_code == 403

    def test_upload_unauthenticated_401(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
        )
        assert resp.status_code == 401

    def test_upload_no_files_400(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents", headers=auth_headers
        )
        # FastAPI multipart parser возвращает 422 если нет файлов в сигнатуре `...`
        assert resp.status_code in {400, 422}


class TestListDocuments:
    def test_list_empty(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/documents", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["documents"] == []

    def test_list_after_upload(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files=[
                ("files", ("a.md", b"alpha", "text/markdown")),
                ("files", ("b.json", b'{"x":1}', "application/json")),
            ],
            headers=auth_headers,
        )
        resp = client.get(f"/api/v1/setup/{sid}/documents", headers=auth_headers)
        body = resp.json()
        assert body["count"] == 2
        filenames = [d["filename"] for d in body["documents"]]
        assert filenames == ["a.md", "b.json"]
        # Регулярному пользователю storage_path скрыт
        assert all(d["storage_path"] is None for d in body["documents"])

    def test_list_unknown_job_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/v1/setup/nope/documents", headers=auth_headers)
        assert resp.status_code == 404

    def test_list_other_user_403(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        other = {"X-User-Id": "u2", "X-Roles": "user"}
        resp = client.get(f"/api/v1/setup/{sid}/documents", headers=other)
        assert resp.status_code == 403

    def test_admin_sees_storage_paths(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        resp = client.get(f"/api/v1/setup/{sid}/documents", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["documents"][0]["storage_path"] is not None
        assert "s3://" in body["documents"][0]["storage_path"]
