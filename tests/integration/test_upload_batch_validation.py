"""Integration: batch-level validation в роутере (T-S02-005, T-S02-006).

Проверяет, что:
- BATCH_TOO_LARGE (по count и size) → 413 на batch-уровне
- filename uniqueness в batch → 400 INVALID_FILENAME
- partial success: некоторые файлы fail → 201 с errors[]
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.common.defaults import MAX_BATCH_FILES_COUNT

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Batch Validation KB"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


class TestBatchCountLimit:
    def test_too_many_files_returns_413(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        # MAX + 1 файлов
        files = [
            (
                "files",
                (f"doc_{i}.md", f"content {i}".encode(), "text/markdown"),
            )
            for i in range(MAX_BATCH_FILES_COUNT + 1)
        ]
        resp = client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        assert resp.status_code == 413
        detail = resp.json()["detail"]
        assert detail["error_code"] == "BATCH_TOO_LARGE"
        assert detail["details"]["reason"] == "too_many_files"


class TestFilenameUniqueness:
    def test_duplicate_filename_in_batch_returns_400(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        files = [
            ("files", ("same.md", b"first", "text/markdown")),
            ("files", ("same.md", b"second", "text/markdown")),
        ]
        resp = client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error_code"] == "INVALID_FILENAME"
        assert detail["details"]["reason"] == "duplicate_in_batch"

    def test_unique_filenames_ok(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        files = [
            ("files", ("a.md", b"first", "text/markdown")),
            ("files", ("b.md", b"second", "text/markdown")),
        ]
        resp = client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["summary"]["files_uploaded"] == 2


class TestPartialSuccess:
    def test_mixed_valid_and_invalid_returns_201_with_errors(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        files = [
            ("files", ("good.md", b"content", "text/markdown")),
            ("files", ("bad.exe", b"binary", "application/x-msdownload")),
            ("files", ("empty.md", b"", "text/markdown")),
        ]
        resp = client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["summary"]["files_total"] == 3
        assert body["summary"]["files_uploaded"] == 1
        assert body["summary"]["files_rejected"] == 2
        # Errors structured per spec
        codes = sorted(e["error_code"] for e in body["errors"])
        assert codes == ["EMPTY_FILE", "UNSUPPORTED_FILE_TYPE"]
        # Good file всё равно сохранён
        assert len(body["uploaded"]) == 1
        assert body["uploaded"][0]["filename"] == "good.md"


class TestSafetyChecks:
    def test_path_traversal_filename_per_file_error(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        # FastAPI/Starlette санитизирует filename в multipart (убирает path
        # separators при формировании Content-Disposition). Чтобы проверить
        # backend-уровень валидации, эмулируем напрямую путём передачи имени
        # с `..` (не path separator).
        files = [
            ("files", ("..weird.md", b"content", "text/markdown")),
        ]
        resp = client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["summary"]["files_rejected"] == 1
        assert body["errors"][0]["error_code"] == "INVALID_FILENAME"
        assert body["errors"][0]["details"]["reason"] == "forbidden_sequence"
