"""Integration: source.document.* events publication (T-S03-020)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep
from schemas.setup.source_document import SourceDocumentStatus

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Events KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


def _bus(app):
    from fe_bot.api.dependencies import get_event_bus

    return app.dependency_overrides[get_event_bus]()


def _lifecycle(app):
    from fe_bot.api.dependencies import get_source_lifecycle

    return app.dependency_overrides[get_source_lifecycle]()


def _events_of_type(bus, event_type: str) -> list:
    return [e for e in bus.history() if e.event_type == event_type]


class TestRegisteredEvent:
    def test_upload_publishes_registered(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        _upload(client, sid, auth_headers)
        events = _events_of_type(
            _bus(app_with_clean_state), "source.document.registered"
        )
        assert len(events) == 1
        assert events[0].setup_job_id == sid


class TestStatusChangedEvent:
    def test_subsequent_transition_publishes_status_changed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        # registered (auto) → parsing (manual)
        _lifecycle(app_with_clean_state).update_status(
            source_document_id=doc_id,
            new_status=SourceDocumentStatus.PARSING,
            event_id="evt_change_1",
            reason="Parser started",
        )
        events = _events_of_type(
            _bus(app_with_clean_state), "source.document.status_changed"
        )
        assert len(events) == 1
        assert events[0].metrics["new_status"] == "parsing"
        assert events[0].metrics["old_status"] == "registered"


class TestMetadataUpdatedEvent:
    def test_patch_metadata_publishes_event(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ["new"]},
            headers=auth_headers,
        )
        events = _events_of_type(
            _bus(app_with_clean_state), "source.document.metadata_updated"
        )
        assert len(events) == 1
        assert "tags" in events[0].metrics["fields_changed"]


class TestLineageUpdatedEvent:
    def test_link_artifact_publishes_event(
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
        events = _events_of_type(
            _bus(app_with_clean_state), "source.document.lineage_updated"
        )
        assert len(events) == 1
        assert events[0].metrics["target_type"] == "rag_card"

    def test_idempotent_link_does_not_double_publish(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_1",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_link",
            created_by_service="gen",
        )
        svc.link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_1",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_link",  # тот же event_id
            created_by_service="gen",
        )
        events = _events_of_type(
            _bus(app_with_clean_state), "source.document.lineage_updated"
        )
        assert len(events) == 1


class TestProcessingFailedEvent:
    def test_error_log_publishes_processing_failed(
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
            message="Parser crashed",
            event_id="evt_err",
            level=ProcessingLogLevel.ERROR,
            error_code="PARSE_FAILED",
        )
        events = _events_of_type(
            _bus(app_with_clean_state), "source.document.processing_failed"
        )
        assert len(events) == 1
        assert events[0].metrics["error_code"] == "PARSE_FAILED"

    def test_info_log_does_not_publish_processing_failed(
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
            message="Parsing started",
            event_id="evt_info",
            level=ProcessingLogLevel.INFO,
        )
        events = _events_of_type(
            _bus(app_with_clean_state), "source.document.processing_failed"
        )
        assert len(events) == 0
