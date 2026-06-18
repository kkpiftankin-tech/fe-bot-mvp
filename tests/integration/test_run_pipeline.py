"""Integration: POST /api/v1/setup/{id}/run (T-S01-022).

Использует fallback-only generator из conftest — без обращения к Ollama.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _upload_md(
    client: TestClient,
    headers: dict[str, str],
    *,
    project_name: str = "Test KB",
    contents: list[tuple[str, bytes]] | None = None,
) -> str:
    """Создаёт job, загружает документы, возвращает setup_job_id."""
    create = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": project_name},
        headers=headers,
    )
    sid = create.json()["setup_job_id"]
    if contents is None:
        contents = [("doc.md", b"# Task description\n\nSome body text.")]
    files = [("files", (name, data, "text/markdown")) for name, data in contents]
    up = client.post(
        f"/api/v1/setup/{sid}/documents",
        files=files,
        headers=headers,
    )
    assert up.status_code == 201, up.json()
    return sid


class TestRunPipelineHappyPath:
    def test_run_returns_pipeline_summary(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _upload_md(client, auth_headers)
        resp = client.post(f"/api/v1/setup/{sid}/run", headers=auth_headers)
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["setup_job_id"] == sid
        # В fallback-only режиме (S4): cards = review_required → pipeline дошёл
        # до validation и перешёл в REVIEW_REQUIRED.
        assert body["final_status"] == "review_required"
        assert body["documents_total"] == 1
        assert body["documents_parsed"] == 1
        assert body["documents_failed"] == 0
        assert body["sections_extracted"] >= 1
        assert body["cards_generated"] >= 1
        assert body["cards_review_required"] >= 1
        assert body["cards_used_fallback"] >= 1

    def test_run_advances_job_status(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _upload_md(client, auth_headers)
        client.post(f"/api/v1/setup/{sid}/run", headers=auth_headers)
        # job-статус прошёл parsing → sections_extracted → rag_cards_generating
        # → metadata_validating → review_required (fallback карточки low confidence)
        status_resp = client.get(f"/api/v1/setup/{sid}", headers=auth_headers)
        assert status_resp.json()["status"] == "review_required"

    def test_run_multiple_documents(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _upload_md(
            client,
            auth_headers,
            contents=[
                ("a.md", b"# Schema definition\n\nfield: foo\n"),
                ("b.md", b"# Validation rules\n\n- check x"),
            ],
        )
        resp = client.post(f"/api/v1/setup/{sid}/run", headers=auth_headers)
        body = resp.json()
        assert body["documents_total"] == 2
        assert body["documents_parsed"] == 2
        assert body["sections_extracted"] >= 2


class TestRunPipelineErrors:
    def test_run_on_draft_returns_409(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # Job создан, но документов нет — статус остался draft.
        create = client.post(
            "/api/v1/setup/jobs",
            json={"project_name": "Empty"},
            headers=auth_headers,
        )
        sid = create.json()["setup_job_id"]
        resp = client.post(f"/api/v1/setup/{sid}/run", headers=auth_headers)
        assert resp.status_code == 409
        assert "Upload at least one" in resp.json()["detail"]

    def test_run_unknown_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post("/api/v1/setup/nope/run", headers=auth_headers)
        assert resp.status_code == 404

    def test_run_requires_setup_run_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _upload_md(client, auth_headers)
        auditor_headers = {"X-User-Id": "auditor1", "X-Roles": "auditor"}
        resp = client.post(f"/api/v1/setup/{sid}/run", headers=auditor_headers)
        assert resp.status_code == 403

    def test_run_other_user_job_returns_403(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _upload_md(client, auth_headers)
        other = {"X-User-Id": "u2", "X-Roles": "user"}
        resp = client.post(f"/api/v1/setup/{sid}/run", headers=other)
        assert resp.status_code == 403

    def test_run_admin_can_run_others_job(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
    ) -> None:
        sid = _upload_md(client, auth_headers)
        resp = client.post(f"/api/v1/setup/{sid}/run", headers=admin_headers)
        assert resp.status_code == 200


class TestRunPipelineFailedParse:
    def test_unsupported_format_fails_one_document(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        # PDF stub → UnsupportedFormatError.
        create = client.post(
            "/api/v1/setup/jobs",
            json={"project_name": "Mixed formats"},
            headers=auth_headers,
        )
        sid = create.json()["setup_job_id"]
        files = [
            ("files", ("good.md", b"# Title\n\nbody", "text/markdown")),
            ("files", ("bad.pdf", b"%PDF-1.4", "application/pdf")),
        ]
        client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)

        resp = client.post(f"/api/v1/setup/{sid}/run", headers=auth_headers)
        body = resp.json()
        assert body["documents_total"] == 2
        assert body["documents_parsed"] == 1
        assert body["documents_failed"] == 1
        assert any("PARSE[bad.pdf]" in e for e in body["errors"])
        # Pipeline всё равно завершается успешно (один документ распарсен) и
        # доходит до review_required (fallback карточки low confidence).
        assert body["final_status"] == "review_required"

    def test_all_documents_fail_pipeline_fails(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        create = client.post(
            "/api/v1/setup/jobs",
            json={"project_name": "All bad"},
            headers=auth_headers,
        )
        sid = create.json()["setup_job_id"]
        files = [
            ("files", ("a.pdf", b"%PDF-1.4", "application/pdf")),
            ("files", ("b.pdf", b"%PDF-1.4 v2", "application/pdf")),
        ]
        client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=auth_headers)
        resp = client.post(f"/api/v1/setup/{sid}/run", headers=auth_headers)
        body = resp.json()
        assert body["documents_failed"] == 2
        assert body["final_status"] == "failed"
