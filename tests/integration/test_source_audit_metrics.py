"""Integration: audit + metrics для Source Registry actions (T-S03-022)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep
from schemas.setup.source_document import SourceDocumentStatus

from fe_bot.audit.service import AuditAction

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Audit KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


def _audit_log(app):
    from fe_bot.api.dependencies import get_audit_log

    return app.dependency_overrides[get_audit_log]()


def _metrics(app):
    from fe_bot.api.dependencies import get_metrics

    return app.dependency_overrides[get_metrics]()


def _lifecycle(app):
    from fe_bot.api.dependencies import get_source_lifecycle

    return app.dependency_overrides[get_source_lifecycle]()


class TestStatusChangedAudit:
    def test_upload_creates_status_changed_audit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """T-S03-019 auto-registration → STATUS_CHANGED audit (UPLOADED→REGISTERED)."""
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        events = [
            e
            for e in _audit_log(app_with_clean_state).list_for_job(sid)
            if e.action == AuditAction.STATUS_CHANGED
        ]
        assert len(events) == 1
        assert events[0].payload["new_status"] == "registered"

    def test_status_changes_total_metric_incremented(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        m = _metrics(app_with_clean_state)
        # uploaded → registered transition.
        assert (
            m.counter_value(
                "source_status_changes_total",
                labels={"from_status": "uploaded", "to_status": "registered"},
            )
            >= 1.0
        )


class TestMetadataUpdatedAudit:
    def test_patch_creates_audit_event(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ["x"], "description": "test"},
            headers=auth_headers,
        )
        events = [
            e
            for e in _audit_log(app_with_clean_state).list_for_job(sid)
            if e.action == AuditAction.METADATA_UPDATED
        ]
        assert len(events) == 1
        assert "tags" in events[0].payload["fields_changed"]
        assert "description" in events[0].payload["fields_changed"]


class TestLineageAddedAuditAndMetrics:
    def test_link_creates_audit_event(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _lifecycle(app_with_clean_state).link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_1",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_link",
            created_by_service="gen",
        )
        events = [
            e
            for e in _audit_log(app_with_clean_state).list_for_job(sid)
            if e.action == AuditAction.LINEAGE_ADDED
        ]
        assert len(events) == 1
        assert events[0].payload["target_type"] == "rag_card"

    def test_lineage_relations_metric_incremented(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _lifecycle(app_with_clean_state).link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_1",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_link",
            created_by_service="gen",
        )
        m = _metrics(app_with_clean_state)
        assert (
            m.counter_value(
                "source_lineage_relations_total",
                labels={"target_type": "rag_card", "relation_type": "generated_from"},
            )
            == 1.0
        )


class TestProcessingFailuresMetric:
    def test_error_log_increments_failures_metric(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        _lifecycle(app_with_clean_state).append_processing_log(
            source_document_id=doc_id,
            setup_job_id=sid,
            step=ProcessingLogStep.PARSING,
            message="boom",
            event_id="evt_err",
            level=ProcessingLogLevel.ERROR,
            error_code="PARSE_TIMEOUT",
        )
        m = _metrics(app_with_clean_state)
        assert (
            m.counter_value(
                "source_processing_failures_total",
                labels={"step": "parsing", "error_code": "PARSE_TIMEOUT"},
            )
            == 1.0
        )


class TestRetryAudit:
    def test_retry_creates_audit_event(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.update_status(
            source_document_id=doc_id,
            new_status=SourceDocumentStatus.PARSING,
            event_id="evt_to_parsing",
        )
        svc.update_status(
            source_document_id=doc_id,
            new_status=SourceDocumentStatus.PROCESSING_FAILED,
            event_id="evt_to_failed",
        )
        client.post(
            f"/api/v1/setup/{sid}/sources/{doc_id}/retry",
            headers=auth_headers,
        )
        events = [
            e
            for e in _audit_log(app_with_clean_state).list_for_job(sid)
            if e.action == AuditAction.PROCESSING_RETRY_TRIGGERED
        ]
        assert len(events) == 1
