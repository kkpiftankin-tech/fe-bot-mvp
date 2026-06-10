"""Integration: upload_request_id idempotency (T-S02-007)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Idempotency KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


class TestIdempotency:
    def test_repeated_request_same_id_returns_cached(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)

        # Первый запрос — нормальный upload.
        first = client.post(
            f"/api/v1/setup/{sid}/documents?upload_request_id=req_001",
            files={"files": ("doc.md", b"content first", "text/markdown")},
            headers=auth_headers,
        )
        assert first.status_code == 201
        first_doc_id = first.json()["uploaded"][0]["source_document_id"]

        # Второй запрос — тот же id, **другой контент**. Должен вернуться
        # кешированный response первого запроса; реальный upload не происходит.
        second = client.post(
            f"/api/v1/setup/{sid}/documents?upload_request_id=req_001",
            files={"files": ("other.md", b"content second", "text/markdown")},
            headers=auth_headers,
        )
        assert second.status_code == 201
        # Тот же source_document_id (это кешированный response).
        assert second.json()["uploaded"][0]["source_document_id"] == first_doc_id
        # И тот же filename — even though мы запросили другой файл.
        assert second.json()["uploaded"][0]["filename"] == "doc.md"

    def test_different_request_id_does_not_use_cache(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        first = client.post(
            f"/api/v1/setup/{sid}/documents?upload_request_id=req_a",
            files={"files": ("a.md", b"a", "text/markdown")},
            headers=auth_headers,
        )
        # Второй с другим request_id → cache miss, новый upload.
        # Используем тот же файл, в результате checksum совпадёт → duplicate.
        second = client.post(
            f"/api/v1/setup/{sid}/documents?upload_request_id=req_b",
            files={"files": ("a.md", b"a", "text/markdown")},
            headers=auth_headers,
        )
        assert second.status_code == 201
        # Сработал duplicate detection (через checksum, не через idempotency cache).
        body = second.json()
        assert body["summary"]["duplicates_detected"] == 1
        assert (
            body["skipped_duplicates"][0]["source_document_id"]
            == first.json()["uploaded"][0]["source_document_id"]
        )

    def test_no_request_id_no_caching(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        # Без request_id — cache не используется.
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"a", "text/markdown")},
            headers=auth_headers,
        )
        second = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("b.md", b"b", "text/markdown")},
            headers=auth_headers,
        )
        # Без cache повторный запрос загружает новый файл.
        assert second.json()["uploaded"][0]["filename"] == "b.md"

    def test_upload_batch_id_is_server_generated(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """T-S02-009: upload_batch_id генерируется сервером (uuid-based),
        не равен upload_request_id. Это разделение ответственности:
        - upload_request_id — клиентский idempotency token.
        - upload_batch_id   — серверный batch identifier для audit / GET.
        """
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents?upload_request_id=req_xyz",
            files={"files": ("a.md", b"x", "text/markdown")},
            headers=auth_headers,
        )
        batch_id = resp.json()["upload_batch_id"]
        assert batch_id is not None
        assert batch_id.startswith("batch_")
        # И не равен request_id.
        assert batch_id != "req_xyz"
