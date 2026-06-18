"""Integration: GET /api/v1/setup/{id} + /progress (T-S01-010)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "KB for tests", "domain": "naval"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["setup_job_id"]


class TestGetSetupJob:
    def test_get_existing_job(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_job_id"] == sid
        assert body["status"] == "draft"
        assert body["project_name"] == "KB for tests"

    def test_get_nonexistent_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/v1/setup/setup_nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_owned_by_other_user_returns_403(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        other = {"X-User-Id": "u2", "X-Roles": "user"}
        resp = client.get(f"/api/v1/setup/{sid}", headers=other)
        assert resp.status_code == 403

    def test_get_admin_can_see_other_users_jobs(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}", headers=admin_headers)
        assert resp.status_code == 200

    def test_get_unauthenticated_returns_401(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}")
        assert resp.status_code == 401


class TestGetSetupProgress:
    def test_progress_includes_status_and_percent(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/progress", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_job_id"] == sid
        assert body["status"] == "draft"
        assert body["progress_percent"] == 0.0
        assert body["current_step"] is None
        assert body["error_count"] == 0

    def test_progress_404_for_unknown(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/v1/setup/nope/progress", headers=auth_headers)
        assert resp.status_code == 404
