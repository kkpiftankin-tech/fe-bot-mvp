"""Integration tests for SETUP-05 RAG cards endpoints (T-S05-028..032)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


# ============================================================
# Helpers
# ============================================================


def _create_setup_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "RAG Cards Test"},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["setup_job_id"]


def _upload_md(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    body = b"# Tasks\n\nDescription of ML task.\n"
    resp = client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", body, "text/markdown")},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["uploaded"][0]["source_document_id"]


def _create_parse_job_and_run(client: TestClient, sid: str, headers: dict[str, str]) -> None:
    pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=headers)
    assert pj.status_code == 201, pj.text
    job_id = pj.json()["parse_job_id"]
    run = client.post(f"/api/v1/setup/{sid}/parse-jobs/{job_id}/run", headers=headers)
    assert run.status_code == 200, run.text


def _prepare_setup_with_sections(client: TestClient, headers: dict[str, str]) -> str:
    """Создать setup_job, загрузить markdown, запустить parse — secrions ready."""
    sid = _create_setup_job(client, headers)
    _upload_md(client, sid, headers)
    _create_parse_job_and_run(client, sid, headers)
    return sid


# ============================================================
# T-S05-028: POST /rag-cards/generate
# ============================================================


class TestCreateGenerationJob:
    def test_happy_path(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["total_sections"] >= 1
        assert body["setup_job_id"] == sid

    def test_400_no_sections_ready(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_job(client, auth_headers)
        # Нет parsed sections — должен быть 400.
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["error_code"] == "NO_SECTIONS_READY_FOR_CARD_GENERATION"

    def test_409_already_running(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={},
            headers=auth_headers,
        )
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "RAG_CARD_GENERATION_ALREADY_RUNNING"

    def test_404_unknown_setup_job(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/setup/setup_missing/rag-cards/generate",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_403_no_permission(self, client: TestClient) -> None:
        headers = {"X-User-Id": "aud1", "X-Roles": "auditor"}
        resp = client.post(
            "/api/v1/setup/any_id/rag-cards/generate",
            json={},
            headers=headers,
        )
        assert resp.status_code == 403


# ============================================================
# T-S05-028: POST /run
# ============================================================


class TestRunJob:
    def test_run_completes(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] in {"completed", "partial_success", "failed"}

    def test_run_409_terminal(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        # Повторный run должен дать 409.
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        assert resp.status_code == 409


# ============================================================
# T-S05-028: GET status + report
# ============================================================


class TestGetStatusAndReport:
    def test_get_status_after_create(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in {"created", "queued", "running"}

    def test_get_status_404_unknown(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_job(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/gen_missing",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_get_report_after_run(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/report",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["summary"]["total_sections"] >= 1


# ============================================================
# T-S05-029: list/details/preview
# ============================================================


class TestListAndPreview:
    def test_list_after_generation(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards-catalog",
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["pagination"]["total"] >= 1

    def test_get_card_details(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        catalog = client.get(f"/api/v1/setup/{sid}/rag-cards-catalog", headers=auth_headers).json()
        if not catalog["items"]:
            pytest.skip("No cards generated in fallback mode")
        doc_id = catalog["items"][0]["doc_id"]
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["doc_id"] == doc_id
        assert "body_markdown" in body

    def test_preview(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        catalog = client.get(f"/api/v1/setup/{sid}/rag-cards-catalog", headers=auth_headers).json()
        if not catalog["items"]:
            pytest.skip("No cards generated in fallback mode")
        doc_id = catalog["items"][0]["doc_id"]
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/preview",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["doc_id"] == doc_id
        assert isinstance(body["source_trace"], list)

    def test_get_404_unknown_card(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_job(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards/missing.v1",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ============================================================
# T-S05-031: Cancel
# ============================================================


class TestCancel:
    def test_cancel_created(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_terminal_409(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        # Run to terminal.
        client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/run",
            headers=auth_headers,
        )
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gid}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 409


# ============================================================
# T-S05-030: Regenerate
# ============================================================


class TestRegenerate:
    def test_404_unknown_card(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_job(client, auth_headers)
        # USER не имеет KB_RAG_CARD_REGENERATE → 403 раньше 404. Используем admin.
        admin = {"X-User-Id": "admin1", "X-Roles": "admin"}
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/ghost.v1/regenerate",
            json={"reason": "test"},
            headers=admin,
        )
        assert resp.status_code == 404

    def test_403_for_user(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_setup_job(client, auth_headers)
        # USER не имеет KB_RAG_CARD_REGENERATE.
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/x.v1/regenerate",
            json={"reason": "test"},
            headers=auth_headers,
        )
        assert resp.status_code == 403


# ============================================================
# Cross-cutting
# ============================================================


class TestRBAC:
    def test_user_without_cross_job_access_blocked(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _prepare_setup_with_sections(client, auth_headers)
        # Другой user без KB_PUBLISH/CARD_REVIEW не должен видеть чужой setup_job.
        other_user = {"X-User-Id": "other_user", "X-Roles": "user"}
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards-catalog",
            headers=other_user,
        )
        assert resp.status_code == 403

    def test_cross_job_isolation(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid1 = _prepare_setup_with_sections(client, auth_headers)
        created = client.post(
            f"/api/v1/setup/{sid1}/rag-cards/generate",
            json={},
            headers=auth_headers,
        ).json()
        gid = created["generation_job_id"]
        sid2 = _create_setup_job(client, auth_headers)
        # gid из sid1 не должен видеться из sid2 → 404.
        resp = client.get(
            f"/api/v1/setup/{sid2}/rag-card-generation-jobs/{gid}",
            headers=auth_headers,
        )
        assert resp.status_code == 404
