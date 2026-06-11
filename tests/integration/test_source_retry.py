"""Integration: POST /sources/{id}/retry (T-S03-021).

Closes T-S02-016 which was deferred from SETUP-02.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.source_document import SourceDocumentStatus

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Retry KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


def _force_failed(app, doc_id: str) -> None:
    """Прямой переход документа в PROCESSING_FAILED (для теста retry)."""
    from fe_bot.api.dependencies import get_source_lifecycle

    svc = app.dependency_overrides[get_source_lifecycle]()
    # registered (auto после upload) → parsing → processing_failed
    svc.update_status(
        source_document_id=doc_id,
        new_status=SourceDocumentStatus.PARSING,
        event_id=f"evt_force_parsing_{doc_id}",
    )
    svc.update_status(
        source_document_id=doc_id,
        new_status=SourceDocumentStatus.PROCESSING_FAILED,
        event_id=f"evt_force_failed_{doc_id}",
        reason="Simulated failure for retry test",
    )


class TestRetryHappyPath:
    def test_failed_doc_can_be_retried(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _force_failed(app_with_clean_state, doc_id)

        resp = client.post(
            f"/api/v1/setup/{sid}/sources/{doc_id}/retry?from_step=parsing",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "waiting_for_parsing"
        assert body["from_step"] == "parsing"

    def test_retry_writes_log_entry(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from schemas.setup.processing_log import ProcessingLogStep

        from fe_bot.api.dependencies import get_processing_log_repo

        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _force_failed(app_with_clean_state, doc_id)
        client.post(
            f"/api/v1/setup/{sid}/sources/{doc_id}/retry",
            headers=auth_headers,
        )
        logs = app_with_clean_state.dependency_overrides[
            get_processing_log_repo
        ]().list_for_document(doc_id, step=ProcessingLogStep.RETRY)
        assert len(logs) == 1
        assert "u1" in logs[0].message


class TestRetryStateValidation:
    def test_retry_when_not_failed_returns_409(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Документ в REGISTERED (после upload) — retry не разрешён."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/sources/{doc_id}/retry",
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "INVALID_RETRY_STATE"


class TestRetryIdempotency:
    def test_same_event_id_is_idempotent(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from schemas.setup.processing_log import ProcessingLogStep

        from fe_bot.api.dependencies import get_processing_log_repo

        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _force_failed(app_with_clean_state, doc_id)
        # Первый retry.
        client.post(
            f"/api/v1/setup/{sid}/sources/{doc_id}/retry?event_id=retry_xyz",
            headers=auth_headers,
        )
        # Второй с тем же event_id — no-op.
        client.post(
            f"/api/v1/setup/{sid}/sources/{doc_id}/retry?event_id=retry_xyz",
            headers=auth_headers,
        )
        retry_logs = app_with_clean_state.dependency_overrides[
            get_processing_log_repo
        ]().list_for_document(doc_id, step=ProcessingLogStep.RETRY)
        assert len(retry_logs) == 1


class TestRetryAccessControl:
    def test_unknown_doc_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/sources/src_nope/retry", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_auditor_no_retry_permission(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.post(
            f"/api/v1/setup/{sid}/sources/{doc_id}/retry",
            headers={"X-User-Id": "auditor1", "X-Roles": "auditor"},
        )
        assert resp.status_code == 403
