"""Integration: Metrics для upload-flow (T-S02-012)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Metrics KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


def _metrics(app):
    from fe_bot.api.dependencies import get_metrics

    return app.dependency_overrides[get_metrics]()


class TestUploadCounters:
    def test_successful_upload_increments_uploaded_counter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"content", "text/markdown")},
            headers=auth_headers,
        )
        m = _metrics(app_with_clean_state)
        assert m.counter_value("upload_files_total", labels={"outcome": "uploaded"}) == 1.0
        assert m.counter_value("upload_bytes_total", labels={"outcome": "uploaded"}) == float(
            len(b"content")
        )

    def test_rejected_file_increments_rejected_counter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("bad.exe", b"x", "application/x-msdownload")},
            headers=auth_headers,
        )
        m = _metrics(app_with_clean_state)
        assert m.counter_value("upload_files_total", labels={"outcome": "rejected"}) == 1.0
        assert (
            m.counter_value(
                "upload_errors_total",
                labels={"error_code": "UNSUPPORTED_FILE_TYPE"},
            )
            == 1.0
        )

    def test_duplicate_increments_duplicate_counter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        m = _metrics(app_with_clean_state)
        assert m.counter_value("upload_files_total", labels={"outcome": "duplicate"}) == 1.0

    def test_batch_increments_requests_counter(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        m = _metrics(app_with_clean_state)
        assert m.counter_value("upload_requests_total", labels={"outcome": "completed"}) == 1.0


class TestUploadHistograms:
    def test_file_size_histogram_observed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"contents", "text/markdown")},
            headers=auth_headers,
        )
        m = _metrics(app_with_clean_state)
        assert m.histogram_count("upload_file_size_bytes") == 1
        assert m.histogram_sum("upload_file_size_bytes") == float(len(b"contents"))

    def test_latency_phases_recorded(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        m = _metrics(app_with_clean_state)
        for phase in ("validation", "checksum", "storage", "registry", "total"):
            assert m.histogram_count("upload_latency_seconds", labels={"phase": phase}) == 1, (
                f"phase {phase!r} histogram not recorded"
            )


class TestPrometheusExposition:
    def test_metrics_endpoint_shows_upload_counters(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid = _create_job(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        resp = client.get("/metrics")
        text = resp.text
        assert "upload_files_total" in text
        assert 'outcome="uploaded"' in text
        assert "upload_requests_total" in text
        assert "upload_file_size_bytes_bucket" in text  # histogram bucket
