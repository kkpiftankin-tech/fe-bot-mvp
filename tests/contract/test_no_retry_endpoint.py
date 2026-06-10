"""Contract: /documents/retry отсутствует в OpenAPI (T-S02-016 DEFERRED).

T-S02-016 перенесён в SETUP-03 / S5 (см. docs/implementation-plan/SETUP-02.tasks.md).
Этот negative contract-test явно фиксирует решение: пока не реализованы
persistence исходных байт + реальные failure modes, endpoint **не должен**
существовать. Любое случайное добавление заглушки 501 или real handler'а
сразу упадёт здесь.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fe_bot.app import create_app

pytestmark = pytest.mark.unit


@pytest.fixture
def openapi_spec() -> dict:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/openapi.json")
    return resp.json()


class TestRetryEndpointAbsent:
    def test_retry_path_not_in_openapi(self, openapi_spec: dict) -> None:
        """T-S02-016 deferred. Если этот тест упал — значит endpoint появился
        без обновления плана. Откатывайте либо обновляйте план."""
        paths = openapi_spec["paths"]
        retry_paths = [p for p in paths if "/retry" in p and "/documents" in p]
        assert retry_paths == [], (
            f"/documents/retry endpoint появился в OpenAPI: {retry_paths}. "
            "T-S02-016 deferred — обновите SETUP-02.tasks.md перед добавлением."
        )

    def test_retry_request_returns_405_not_501(
        self,
    ) -> None:
        """POST на отсутствующий путь — 405 Method Not Allowed (если GET есть)
        или 404. Не должно быть 501 (что означало бы заглушку)."""
        app = create_app()
        client = TestClient(app)
        # Создадим job чтобы убрать 404 на setup_job_id mismatch.
        create = client.post(
            "/api/v1/setup/jobs",
            json={"project_name": "Retry Probe"},
            headers={"X-User-Id": "u1", "X-Roles": "user"},
        )
        sid = create.json()["setup_job_id"]
        resp = client.post(
            f"/api/v1/setup/{sid}/documents/retry",
            headers={"X-User-Id": "u1", "X-Roles": "user"},
        )
        # Allowed: 404 (path not found) или 405 (method not allowed для path
        # с другими methods). НЕ 501 (это бы означало заглушку Not Implemented).
        assert resp.status_code in (404, 405), (
            f"Expected 404/405 for absent endpoint; got {resp.status_code}."
        )
