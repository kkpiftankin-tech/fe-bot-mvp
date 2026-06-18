"""Integration: PATCH /sources/{id}/metadata (T-S03-017)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Patch KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


class TestPatchMetadataHappyPath:
    def test_patch_tags_succeeds(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ["naval", "schema"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_metadata"]["tags"] == ["naval", "schema"]

    def test_patch_description(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"description": "Описание документа"},
            headers=auth_headers,
        )
        assert resp.json()["user_metadata"]["description"] == "Описание документа"

    def test_partial_patch_preserves_others(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        # Сначала full patch.
        client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ["a"], "description": "first"},
            headers=auth_headers,
        )
        # Затем только tags.
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ["b"]},
            headers=auth_headers,
        )
        body = resp.json()
        assert body["user_metadata"]["tags"] == ["b"]
        assert body["user_metadata"]["description"] == "first"


class TestPatchProtectedFields:
    def test_extra_field_rejected_400(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"checksum": "evil_value"},
            headers=auth_headers,
        )
        assert resp.status_code == 422  # Pydantic extra=forbid

    def test_xss_sanitized_in_description(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"description": "<script>alert(1)</script>"},
            headers=auth_headers,
        )
        desc = resp.json()["user_metadata"]["description"]
        assert "<script>" not in desc
        assert "&lt;" in desc

    def test_tag_too_long_400(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        """Tag validation в lifecycle (через SourceDocumentUserMetadata) → 400."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ["x" * 200]},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "INVALID_METADATA_PATCH"


class TestPatchAccessControl:
    def test_unknown_doc_404(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/src_nope/metadata",
            json={"tags": ["x"]},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_cross_job_doc_404(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid1 = _create_job(client, auth_headers)
        sid2 = _create_job(client, auth_headers)
        doc_id = _upload(client, sid1, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid2}/sources/{doc_id}/metadata",
            json={"tags": ["x"]},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_auditor_no_patch_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ["x"]},
            headers={"X-User-Id": "auditor1", "X-Roles": "auditor"},
        )
        # Auditor имеет SOURCE_READ, но не METADATA_UPDATE.
        assert resp.status_code == 403
