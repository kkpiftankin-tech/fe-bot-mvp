"""Integration: POST /api/v1/setup/{id}/rag-cards/{doc_id}/review (T-S01-026)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _create_job_and_get_card(
    client: TestClient, headers: dict[str, str]
) -> tuple[str, str]:
    """Создаёт job, прогоняет pipeline, возвращает (setup_job_id, doc_id первой карточки)."""
    create = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Review test KB"},
        headers=headers,
    )
    sid = create.json()["setup_job_id"]
    files = [
        ("files", ("doc.md", b"# Schema fields\n\nf1, f2\n", "text/markdown")),
    ]
    client.post(f"/api/v1/setup/{sid}/documents", files=files, headers=headers)
    client.post(f"/api/v1/setup/{sid}/run", headers=headers)
    cards = client.get(f"/api/v1/setup/{sid}/rag-cards", headers=headers).json()
    return sid, cards["cards"][0]["doc_id"]


def _expert_headers() -> dict[str, str]:
    return {"X-User-Id": "expert1", "X-Roles": "domain_expert"}


class TestApprove:
    def test_approve_review_required_card(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, doc_id = _create_job_and_get_card(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/review",
            json={"decision": "approve", "comment": "looks good"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["decision"] == "approve"
        assert body["affected_doc_id"] == doc_id
        assert body["new_status"] == "approved"
        assert body["new_doc_id"] is None


class TestReject:
    def test_reject_marks_deprecated(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, doc_id = _create_job_and_get_card(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/review",
            json={"decision": "reject", "comment": "wrong domain"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "deprecated"


class TestEdit:
    def test_edit_creates_new_version(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, doc_id = _create_job_and_get_card(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/review",
            json={
                "decision": "edit",
                "updated_body_markdown": "# Schema\n\nfixed",
                "comment": "minor fix",
            },
            headers=_expert_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["new_doc_id"] is not None
        assert body["new_doc_id"] != doc_id
        assert body["new_status"] == "approved"

    def test_edit_without_payload_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, doc_id = _create_job_and_get_card(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/review",
            json={"decision": "edit"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 422


class TestRegenerate:
    def test_regenerate_returns_to_draft(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, doc_id = _create_job_and_get_card(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/review",
            json={"decision": "regenerate", "comment": "redo"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["new_status"] == "draft"


class TestErrors:
    def test_unknown_card_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, _ = _create_job_and_get_card(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/nope.v1/review",
            json={"decision": "approve"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 404

    def test_card_from_other_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid1, doc1 = _create_job_and_get_card(client, auth_headers)
        sid2, _ = _create_job_and_get_card(client, auth_headers)
        # doc1 принадлежит sid1, не sid2 → 404.
        resp = client.post(
            f"/api/v1/setup/{sid2}/rag-cards/{doc1}/review",
            json={"decision": "approve"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 404
        _ = sid1  # silence unused

    def test_basic_user_lacks_review_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, doc_id = _create_job_and_get_card(client, auth_headers)
        # auth_headers = роль user, без kb.card.review
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/review",
            json={"decision": "approve"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_invalid_decision_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid, doc_id = _create_job_and_get_card(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/review",
            json={"decision": "garbage"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 422

    def test_unknown_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.post(
            "/api/v1/setup/unknown/rag-cards/doc.v1/review",
            json={"decision": "approve"},
            headers=_expert_headers(),
        )
        assert resp.status_code == 404
