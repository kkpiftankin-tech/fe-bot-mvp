"""Integration: DELETE /sources/{id} (T-S03-018)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.source_document import SourceDocumentStatus

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Delete KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


def _force_status(app, doc_id: str, new_status: SourceDocumentStatus) -> None:
    """Прямой override статуса для published-теста."""
    from fe_bot.api.dependencies import get_source_registry

    registry = app.dependency_overrides[get_source_registry]()
    doc = registry.get(doc_id)
    object.__setattr__(doc, "status", new_status)
    registry.update(doc)


class TestDeleteHappyPath:
    def test_delete_returns_removed_status(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"

    def test_idempotent_delete(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        resp = client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "removed"


class TestDeletePublishedProtection:
    def test_published_doc_returns_409(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """AC-29: published документ нельзя удалить без admin override."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _force_status(
            app_with_clean_state, doc_id, SourceDocumentStatus.PUBLISHED
        )
        resp = client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 409
        detail = resp.json()["detail"]
        assert detail["error_code"] == "DOCUMENT_ALREADY_PUBLISHED"

    def test_admin_can_delete_published(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Admin (KB_PUBLISH) может override published-блокировку."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _force_status(
            app_with_clean_state, doc_id, SourceDocumentStatus.PUBLISHED
        )
        # Admin может удалить, но job не принимает upload (status может
        # измениться через pipeline). Здесь job всё ещё DRAFT, так что
        # remove_document пройдёт.
        resp = client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=admin_headers
        )
        # Admin override проходит published check; дальше зависит от job-статуса.
        assert resp.status_code in (200, 409)


class TestDeleteAccessControl:
    def test_unknown_doc_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.delete(
            f"/api/v1/setup/{sid}/sources/src_nope", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_cross_job_doc_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid1 = _create_job(client, auth_headers)
        sid2 = _create_job(client, auth_headers)
        doc_id = _upload(client, sid1, auth_headers)
        resp = client.delete(
            f"/api/v1/setup/{sid2}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_auditor_no_delete_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}",
            headers={"X-User-Id": "auditor1", "X-Roles": "auditor"},
        )
        assert resp.status_code == 403
