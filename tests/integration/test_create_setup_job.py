"""Integration: POST /api/v1/setup/jobs (T-S01-009)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "project_name": "Naval Radar KB",
        "domain": "naval",
    }
    base.update(overrides)
    return base


class TestCreateSetupJob:
    def test_create_returns_201_with_setup_job_id(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post("/api/v1/setup/jobs", json=_payload(), headers=auth_headers)
        assert response.status_code == 201
        body = response.json()
        assert body["setup_job_id"].startswith("setup_")
        assert body["status"] == "draft"
        assert body["project_name"] == "Naval Radar KB"
        assert body["progress_percent"] == 0.0
        assert body["user_id"] == "u1"

    def test_create_without_auth_returns_401(self, client: TestClient) -> None:
        response = client.post("/api/v1/setup/jobs", json=_payload())
        assert response.status_code == 401

    def test_create_with_short_project_name_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/setup/jobs",
            json=_payload(project_name="ab"),
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_with_auditor_role_returns_403(self, client: TestClient) -> None:
        # auditor не имеет kb.setup.create
        response = client.post(
            "/api/v1/setup/jobs",
            json=_payload(),
            headers={"X-User-Id": "a1", "X-Roles": "auditor"},
        )
        assert response.status_code == 403

    def test_create_with_unknown_field_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/setup/jobs",
            json={**_payload(), "unexpected_field": "x"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_invalid_review_policy_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/setup/jobs",
            json=_payload(review_policy="loose"),
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_admin_can_also_create(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.post("/api/v1/setup/jobs", json=_payload(), headers=admin_headers)
        assert response.status_code == 201
        assert response.json()["user_id"] == "admin1"
