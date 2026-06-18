"""Integration tests for SETUP-04 parse endpoints (T-S04-023..026)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


# ============================================================
# Helpers
# ============================================================


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Parse KB"},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["setup_job_id"]


def _upload(
    client: TestClient,
    setup_job_id: str,
    headers: dict[str, str],
    *,
    filename: str = "doc.md",
    content: bytes = b"# Title\n\nbody text",
    content_type: str = "text/markdown",
) -> str:
    resp = client.post(
        f"/api/v1/setup/{setup_job_id}/documents",
        files={"files": (filename, content, content_type)},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["uploaded"][0]["source_document_id"]


# ============================================================
# T-S04-023: POST /parse-jobs
# ============================================================


class TestCreateParseJob:
    def test_happy_path(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["total_documents"] == 1
        assert body["setup_job_id"] == sid

    def test_409_already_running(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers)
        _upload(
            client,
            sid,
            auth_headers,
            filename="b.md",
            content=b"# Other",
        )
        resp = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers)
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "PARSE_JOB_ALREADY_RUNNING"

    def test_400_no_parseable_docs(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "NO_PARSEABLE_DOCUMENTS"

    def test_404_unknown_setup_job(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/setup/job_missing/parse-jobs",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_403_no_permission(self, client: TestClient) -> None:
        # auditor — без kb.parse.run.
        headers = {"X-User-Id": "aud1", "X-Roles": "auditor"}
        # auditor не может создать job — но нужен существующий setup_job;
        # auditor имеет доступ только на чтение, поэтому 403 будет уже на POST.
        resp = client.post("/api/v1/setup/any_id/parse-jobs", json={}, headers=headers)
        assert resp.status_code == 403


# ============================================================
# T-S04-024: GET status / report
# ============================================================


class TestGetParseJobStatus:
    def test_status_created(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        resp = client.get(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_404_unknown_parse_job(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/parse-jobs/pj_missing",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_report_empty_when_not_run(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        resp = client.get(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/report",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["documents"] == []
        assert body["status"] == "created"


# ============================================================
# T-S04-025: GET sections / POST cancel
# ============================================================


class TestSectionsAndCancel:
    def test_sections_list_empty_before_run(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        resp = client.get(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/sections",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_cancel_created(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/cancel",
            headers={"X-User-Id": "admin1", "X-Roles": "admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_terminal_409(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        # Cancel once → succeeds.
        admin_headers = {"X-User-Id": "admin1", "X-Roles": "admin"}
        client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/cancel",
            headers=admin_headers,
        )
        # Cancel again — terminal.
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/cancel",
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_cancel_403_for_user(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        # USER не имеет KB_PARSE_CANCEL.
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 403


# ============================================================
# T-S04-026: POST retry
# ============================================================


class TestRetryDocument:
    def test_404_unknown_document(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        expert_headers = {"X-User-Id": "e1", "X-Roles": "domain_expert"}
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/documents/src_missing/retry",
            headers=expert_headers,
        )
        # 403 — owner mismatch (expert не владелец setup_job). Это другой path,
        # но он валиден: ошибка приходит до проверки документа.
        # Для прямого 404 повторим под admin'ом.
        admin_headers = {"X-User-Id": "admin1", "X-Roles": "admin"}
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/documents/src_missing/retry",
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_409_not_failed(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        src_id = _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        admin_headers = {"X-User-Id": "admin1", "X-Roles": "admin"}
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/documents/{src_id}/retry",
            headers=admin_headers,
        )
        # PENDING → не FAILED → 409.
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "DOCUMENT_NOT_PARSEABLE_STATUS"

    def test_403_user_no_retry_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        src_id = _upload(client, sid, auth_headers)
        pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=auth_headers).json()
        # USER не имеет KB_PARSE_RETRY.
        resp = client.post(
            f"/api/v1/setup/{sid}/parse-jobs/{pj['parse_job_id']}/documents/{src_id}/retry",
            headers=auth_headers,
        )
        assert resp.status_code == 403
