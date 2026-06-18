"""Integration: UploadBatch tracking через BatchRegistry (T-S02-009).

Проверяет:
- batch создаётся в IN_PROGRESS до начала обработки файлов
- финализируется с правильным terminal status (COMPLETED / PARTIALLY_COMPLETED / FAILED)
- counters в batch соответствуют summary в response
- request_id collision detect: cache expired + existing batch → 409
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.upload_batch import UploadBatchStatus

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Batch Tracking KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


class TestBatchPersistence:
    def test_successful_batch_is_completed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_batch_registry

        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("a.md", b"content", "text/markdown")},
            headers=auth_headers,
        )
        body = resp.json()
        batch_id = body["upload_batch_id"]

        registry = app_with_clean_state.dependency_overrides[get_batch_registry]()
        batch = registry.get(batch_id)
        assert batch.status == UploadBatchStatus.COMPLETED
        assert batch.files_total == 1
        assert batch.files_uploaded == 1
        assert batch.files_rejected == 0
        assert batch.duplicates_detected == 0
        assert batch.finished_at is not None

    def test_partial_batch_is_partially_completed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_batch_registry

        sid = _create_job(client, auth_headers)
        files = [
            ("files", ("good.md", b"ok", "text/markdown")),
            ("files", ("bad.exe", b"bad", "application/x-msdownload")),
        ]
        resp = client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        batch_id = resp.json()["upload_batch_id"]

        registry = app_with_clean_state.dependency_overrides[get_batch_registry]()
        batch = registry.get(batch_id)
        assert batch.status == UploadBatchStatus.PARTIALLY_COMPLETED
        assert batch.files_total == 2
        assert batch.files_uploaded == 1
        assert batch.files_rejected == 1

    def test_all_rejected_batch_is_failed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_batch_registry

        sid = _create_job(client, auth_headers)
        files = [
            ("files", ("a.exe", b"bad", "application/x-msdownload")),
            ("files", ("b.exe", b"bad", "application/x-msdownload")),
        ]
        resp = client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        batch_id = resp.json()["upload_batch_id"]

        registry = app_with_clean_state.dependency_overrides[get_batch_registry]()
        batch = registry.get(batch_id)
        assert batch.status == UploadBatchStatus.FAILED
        assert batch.files_uploaded == 0
        assert batch.files_rejected == 2

    def test_duplicate_only_batch_is_failed_not_completed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Если все файлы duplicates → batch FAILED (нет успешно загруженных).
        Это семантика "uploaded == 0" → FAILED.
        """
        from fe_bot.api.dependencies import get_batch_registry

        sid = _create_job(client, auth_headers)
        # Первый upload — успешный.
        client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("same.md", b"content", "text/markdown")},
            headers=auth_headers,
        )
        # Второй — тот же файл → duplicate.
        resp = client.post(
            f"/api/v1/setup/{sid}/documents",
            files={"files": ("same.md", b"content", "text/markdown")},
            headers=auth_headers,
        )
        batch_id = resp.json()["upload_batch_id"]

        registry = app_with_clean_state.dependency_overrides[get_batch_registry]()
        batch = registry.get(batch_id)
        assert batch.status == UploadBatchStatus.FAILED
        assert batch.duplicates_detected == 1
        assert batch.files_uploaded == 0


class TestBatchListing:
    def test_list_for_job_returns_all_batches(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_batch_registry

        sid = _create_job(client, auth_headers)
        # 3 разных batch-загрузки.
        for i, content in enumerate([b"a", b"b", b"c"]):
            client.post(
                f"/api/v1/setup/{sid}/documents",
                files={"files": (f"doc_{i}.md", content, "text/markdown")},
                headers=auth_headers,
            )

        registry = app_with_clean_state.dependency_overrides[get_batch_registry]()
        batches = registry.list_for_job(sid)
        assert len(batches) == 3
        # Все в COMPLETED.
        assert all(b.status == UploadBatchStatus.COMPLETED for b in batches)


class TestRequestIdReuseConflict:
    def test_reused_request_id_after_cache_expiry_returns_409(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Если idempotency cache очищен, но batch с этим request_id есть
        в BatchRegistry → 409 Conflict (не silent повтор)."""
        from fe_bot.api.dependencies import get_idempotency_cache

        sid = _create_job(client, auth_headers)
        first = client.post(
            f"/api/v1/setup/{sid}/documents?upload_request_id=req_persistent",
            files={"files": ("a.md", b"a", "text/markdown")},
            headers=auth_headers,
        )
        assert first.status_code == 201

        # Симулируем cache eviction (TTL истёк, batch остался в registry).
        cache = app_with_clean_state.dependency_overrides[get_idempotency_cache]()
        cache.clear()

        # Повторный POST с тем же request_id → 409.
        second = client.post(
            f"/api/v1/setup/{sid}/documents?upload_request_id=req_persistent",
            files={"files": ("b.md", b"b", "text/markdown")},
            headers=auth_headers,
        )
        assert second.status_code == 409
        assert "already used" in second.json()["detail"]
