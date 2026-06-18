"""Integration: GET /sources/{id}/status-history (T-S03-014).

Чтобы создать историю, тесты напрямую дёргают SourceLifecycleService
через DI-override (downstream сервисы статусы не двигают до SETUP-04+).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.source_document import SourceDocumentStatus

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "History KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


def _record_transition(app, doc_id: str, new_status: SourceDocumentStatus, event_id: str) -> None:
    from fe_bot.api.dependencies import get_source_lifecycle

    svc = app.dependency_overrides[get_source_lifecycle]()
    svc.update_status(
        source_document_id=doc_id,
        new_status=new_status,
        event_id=event_id,
        reason="test",
    )


class TestStatusHistoryHappyPath:
    def test_history_has_auto_registered_transition(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """T-S03-019: после upload автоматически записывается UPLOADED→REGISTERED."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/status-history",
            headers=auth_headers,
        ).json()
        assert body["pagination"]["total"] == 1
        assert body["items"][0]["new_status"] == "registered"

    def test_records_chronological_transitions(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        # auto registered (T-S03-019) — 1 entry уже есть.
        _record_transition(
            app_with_clean_state,
            doc_id,
            SourceDocumentStatus.PARSING,
            "evt_2",
        )
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/status-history",
            headers=auth_headers,
        ).json()
        # registered (auto) + parsing (manual) = 2.
        assert body["pagination"]["total"] == 2
        assert [i["new_status"] for i in body["items"]] == [
            "registered",
            "parsing",
        ]

    def test_pagination(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _record_transition(
            app_with_clean_state,
            doc_id,
            SourceDocumentStatus.PARSING,
            "evt_2",
        )
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/status-history?page_size=1",
            headers=auth_headers,
        ).json()
        assert len(body["items"]) == 1
        # auto registered + manual parsing = 2.
        assert body["pagination"]["total"] == 2


class TestStatusHistoryErrors:
    def test_unknown_doc_404(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/src_nope/status-history",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_other_user_403(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/status-history",
            headers={"X-User-Id": "u2", "X-Roles": "user"},
        )
        assert resp.status_code == 403
