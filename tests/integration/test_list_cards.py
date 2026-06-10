"""Integration: GET /api/v1/setup/{id}/rag-cards (T-S01-027)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job_and_run(client: TestClient, headers: dict[str, str]) -> str:
    """Создаёт job, грузит markdown, прогоняет pipeline → cards в registry."""
    create = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "List cards KB"},
        headers=headers,
    )
    sid = create.json()["setup_job_id"]
    body = b"# Schema fields\n\nf1, f2\n\n# Validation\n\nrule\n"
    files = [
        ("files", ("doc.md", body, "text/markdown")),
    ]
    client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=headers)
    client.post(f"/api/v1/setup/{sid}/run", headers=headers)
    return sid


class TestListCards:
    def test_list_returns_cards_after_pipeline(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job_and_run(client, auth_headers)
        resp = client.get(f"/api/v1/setup/{sid}/rag-cards", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_job_id"] == sid
        assert body["count"] >= 2  # 2 секции → 2 карточки
        assert len(body["cards"]) == body["count"]
        # У карточек должен быть body_preview, но не полное body.
        for card in body["cards"]:
            assert card["body_markdown"] is None
            assert card["body_preview"] is not None

    def test_include_body_returns_full_markdown(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job_and_run(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards?include=body",
            headers=auth_headers,
        )
        body = resp.json()
        for card in body["cards"]:
            assert card["body_markdown"] is not None
            assert card["body_preview"] is None

    def test_filter_by_status(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job_and_run(client, auth_headers)
        # fallback-only generator → все карточки в review_required после
        # validation (low confidence).
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards?card_status=review_required",
            headers=auth_headers,
        )
        body = resp.json()
        assert body["count"] >= 1
        assert all(c["status"] == "review_required" for c in body["cards"])

    def test_filter_by_doc_type(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job_and_run(client, auth_headers)
        # secondary section с "Validation" → validation_rule_card.
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards?doc_type=validation_rule_card",
            headers=auth_headers,
        )
        body = resp.json()
        assert all(c["doc_type"] == "validation_rule_card" for c in body["cards"])

    def test_unknown_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get("/api/v1/setup/unknown/rag-cards", headers=auth_headers)
        assert resp.status_code == 404

    def test_other_user_job_returns_403(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job_and_run(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards",
            headers={"X-User-Id": "u2", "X-Roles": "user"},
        )
        assert resp.status_code == 403

    def test_auditor_cannot_list(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job_and_run(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/rag-cards",
            headers={"X-User-Id": "x", "X-Roles": "auditor"},
        )
        assert resp.status_code == 403  # нет kb.setup.run
