"""Integration: POST /api/v1/setup/{id}/cancel (T-S01-011)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "KB to cancel"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


class TestCancelSetupJob:
    def test_cancel_draft_job(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(f"/api/v1/setup/{sid}/cancel", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"
        assert body["finished_at"] is not None
        assert body["message"] == "Setup job cancelled"

    def test_cancel_is_idempotent(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        first = client.post(f"/api/v1/setup/{sid}/cancel", headers=auth_headers)
        assert first.status_code == 200
        second = client.post(f"/api/v1/setup/{sid}/cancel", headers=auth_headers)
        assert second.status_code == 200
        assert second.json()["status"] == "cancelled"

    def test_cancel_nonexistent_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post("/api/v1/setup/nope/cancel", headers=auth_headers)
        assert resp.status_code == 404

    def test_cancel_other_user_job_returns_403(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        other = {"X-User-Id": "u2", "X-Roles": "user"}
        resp = client.post(f"/api/v1/setup/{sid}/cancel", headers=other)
        assert resp.status_code == 403

    def test_admin_can_cancel_others_job(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(f"/api/v1/setup/{sid}/cancel", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_unauthenticated_returns_401(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(f"/api/v1/setup/{sid}/cancel")
        assert resp.status_code == 401
