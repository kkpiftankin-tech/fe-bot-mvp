"""Contract: 12 endpoints из SETUP-01 §16.1 зарегистрированы в FastAPI (T-S01-006)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fe_bot.app import create_app

pytestmark = pytest.mark.unit


EXPECTED_PATHS_AND_METHODS: list[tuple[str, str]] = [
    ("/api/v1/setup/jobs", "POST"),
    ("/api/v1/setup/{setup_job_id}", "GET"),
    ("/api/v1/setup/{setup_job_id}/documents", "POST"),
    ("/api/v1/setup/{setup_job_id}/documents", "GET"),
    ("/api/v1/setup/{setup_job_id}/run", "POST"),
    ("/api/v1/setup/{setup_job_id}/progress", "GET"),
    ("/api/v1/setup/{setup_job_id}/rag-cards", "GET"),
    ("/api/v1/setup/{setup_job_id}/rag-cards/{doc_id}/review", "POST"),
    ("/api/v1/setup/{setup_job_id}/retrieval-tests", "POST"),
    ("/api/v1/setup/{setup_job_id}/publish", "POST"),
    ("/api/v1/setup/{setup_job_id}/report", "GET"),
    ("/api/v1/setup/{setup_job_id}/cancel", "POST"),
]


@pytest.fixture
def openapi_spec() -> dict:
    app = create_app()
    client = TestClient(app)
    return client.get("/openapi.json").json()


class TestEndpointsRegistered:
    def test_all_12_endpoints_present(self, openapi_spec: dict) -> None:
        paths = openapi_spec["paths"]
        missing: list[tuple[str, str]] = []
        for path, method in EXPECTED_PATHS_AND_METHODS:
            if path not in paths or method.lower() not in paths[path]:
                missing.append((path, method))
        assert not missing, f"Missing endpoints: {missing}"

    def test_openapi_title(self, openapi_spec: dict) -> None:
        assert openapi_spec["info"]["title"] == "FE-Bot API"

    def test_setup_tag_present(self, openapi_spec: dict) -> None:
        paths = openapi_spec["paths"]
        for path, method in EXPECTED_PATHS_AND_METHODS:
            tags = paths[path][method.lower()].get("tags", [])
            assert "setup" in tags, f"{method} {path} missing 'setup' tag"


class TestImplementedEndpointsHaveStatusCodes:
    def test_create_job_201(self, openapi_spec: dict) -> None:
        op = openapi_spec["paths"]["/api/v1/setup/jobs"]["post"]
        assert "201" in op["responses"]

    def test_get_job_200(self, openapi_spec: dict) -> None:
        op = openapi_spec["paths"]["/api/v1/setup/{setup_job_id}"]["get"]
        assert "200" in op["responses"]

    def test_cancel_200(self, openapi_spec: dict) -> None:
        op = openapi_spec["paths"]["/api/v1/setup/{setup_job_id}/cancel"]["post"]
        assert "200" in op["responses"]
