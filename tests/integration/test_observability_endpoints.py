"""Integration: /metrics, /healthz, /readyz + RequestContextMiddleware (T-S01-049, T-S01-050)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestHealthEndpoints:
    def test_healthz(self, client: TestClient) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_readyz(self, client: TestClient) -> None:
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}


class TestMetricsEndpoint:
    def test_metrics_returns_text(self, client: TestClient) -> None:
        # Делаем несколько запросов, чтобы накопить метрики.
        client.get("/healthz")
        client.get("/healthz")
        client.get("/readyz")
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        text = resp.text
        # Должен быть Counter http_requests_total + Histogram duration.
        assert "http_requests_total" in text
        assert "http_request_duration_seconds" in text
        assert "GET" in text


class TestRequestIdMiddleware:
    def test_assigns_request_id(self, client: TestClient) -> None:
        resp = client.get("/healthz")
        assert "X-Request-Id" in resp.headers
        assert resp.headers["X-Request-Id"].startswith("req_")

    def test_preserves_existing_request_id(
        self, client: TestClient
    ) -> None:
        resp = client.get("/healthz", headers={"X-Request-Id": "req_custom"})
        assert resp.headers["X-Request-Id"] == "req_custom"


class TestMetricsLabels:
    def test_status_class_label(self, client: TestClient) -> None:
        # 200
        client.get("/healthz")
        # 404
        client.get("/api/v1/setup/nonexistent_job_xxxx", headers={"X-User-Id": "u1"})
        resp = client.get("/metrics")
        text = resp.text
        # Должны быть series для 2xx и 4xx.
        assert 'status_class="2xx"' in text
        assert 'status_class="4xx"' in text
