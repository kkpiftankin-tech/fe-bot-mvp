"""Integration: GET /sources/{id}/processing-log + lineage (T-S03-015)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Log KB"},
        headers=headers,
    ).json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> str:
    return client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", b"content", "text/markdown")},
        headers=headers,
    ).json()["uploaded"][0]["source_document_id"]


def _lifecycle(app):
    from fe_bot.api.dependencies import get_source_lifecycle

    return app.dependency_overrides[get_source_lifecycle]()


# ============================================================
# Processing log
# ============================================================


class TestProcessingLogEndpoint:
    def test_has_only_upload_entry_initially(
        self, client: TestClient, expert_headers: dict[str, str]
    ) -> None:
        """T-S03-019: после upload автоматически есть UPLOAD log entry."""
        sid = _create_job(client, expert_headers)
        doc_id = _upload(client, sid, expert_headers)
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/processing-log",
            headers=expert_headers,
        ).json()
        assert body["pagination"]["total"] == 1
        assert body["items"][0]["step"] == "upload"

    def test_returns_logged_entries(
        self,
        client: TestClient,
        expert_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, expert_headers)
        doc_id = _upload(client, sid, expert_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.append_processing_log(
            source_document_id=doc_id,
            setup_job_id=sid,
            step=ProcessingLogStep.PARSING,
            message="parsing started",
            event_id="evt_log_1",
        )
        svc.append_processing_log(
            source_document_id=doc_id,
            setup_job_id=sid,
            step=ProcessingLogStep.RAG_CARD_GENERATION,
            message="boom",
            event_id="evt_log_2",
            level=ProcessingLogLevel.ERROR,
            error_code="GEN_FAILED",
        )
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/processing-log",
            headers=expert_headers,
        ).json()
        # upload (auto) + parsing + rag = 3.
        assert body["pagination"]["total"] == 3
        steps = sorted(i["step"] for i in body["items"])
        assert steps == ["parsing", "rag_card_generation", "upload"]

    def test_filter_by_step(
        self,
        client: TestClient,
        expert_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, expert_headers)
        doc_id = _upload(client, sid, expert_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.append_processing_log(
            source_document_id=doc_id,
            setup_job_id=sid,
            step=ProcessingLogStep.PARSING,
            message="parsing",
            event_id="evt_1",
        )
        svc.append_processing_log(
            source_document_id=doc_id,
            setup_job_id=sid,
            step=ProcessingLogStep.RAG_CARD_GENERATION,
            message="cards",
            event_id="evt_2",
        )
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/processing-log?step=parsing",
            headers=expert_headers,
        ).json()
        assert body["pagination"]["total"] == 1
        assert body["items"][0]["step"] == "parsing"

    def test_filter_by_level_error(
        self,
        client: TestClient,
        expert_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, expert_headers)
        doc_id = _upload(client, sid, expert_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.append_processing_log(
            source_document_id=doc_id,
            setup_job_id=sid,
            step=ProcessingLogStep.PARSING,
            message="ok",
            event_id="evt_ok",
        )
        svc.append_processing_log(
            source_document_id=doc_id,
            setup_job_id=sid,
            step=ProcessingLogStep.PARSING,
            message="boom",
            event_id="evt_err",
            level=ProcessingLogLevel.ERROR,
        )
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/processing-log?level=error",
            headers=expert_headers,
        ).json()
        assert body["pagination"]["total"] == 1
        assert body["items"][0]["message"] == "boom"

    def test_unknown_doc_404(
        self, client: TestClient, expert_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, expert_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/src_nope/processing-log",
            headers=expert_headers,
        )
        assert resp.status_code == 404


# ============================================================
# Lineage
# ============================================================


class TestLineageEndpoint:
    def test_empty_lineage_for_fresh_doc(
        self, client: TestClient, expert_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, expert_headers)
        doc_id = _upload(client, sid, expert_headers)
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/lineage",
            headers=expert_headers,
        ).json()
        assert body["relations"] == []
        assert body["counters"]["rag_cards_count"] == 0

    def test_lineage_with_relations(
        self,
        client: TestClient,
        expert_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, expert_headers)
        doc_id = _upload(client, sid, expert_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_001",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_lin_1",
            created_by_service="generator",
        )
        svc.link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.PARSED_SECTION,
            target_id="sec_001",
            relation_type=LineageRelationType.PARSED_FROM,
            event_id="evt_lin_2",
            created_by_service="parser",
        )
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/lineage",
            headers=expert_headers,
        ).json()
        assert len(body["relations"]) == 2
        assert body["counters"]["rag_cards_count"] == 1
        assert body["counters"]["parsed_sections_count"] == 1

    def test_lineage_filter_by_target_type(
        self,
        client: TestClient,
        expert_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, expert_headers)
        doc_id = _upload(client, sid, expert_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_001",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_card",
            created_by_service="gen",
        )
        svc.link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.PARSED_SECTION,
            target_id="sec_001",
            relation_type=LineageRelationType.PARSED_FROM,
            event_id="evt_sec",
            created_by_service="parser",
        )
        body = client.get(
            f"/api/v1/setup/{sid}/sources/{doc_id}/lineage?target_type=rag_card",
            headers=expert_headers,
        ).json()
        assert len(body["relations"]) == 1
        assert body["relations"][0]["target_id"] == "card_001"

    def test_unknown_doc_404(
        self, client: TestClient, expert_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, expert_headers)
        resp = client.get(
            f"/api/v1/setup/{sid}/sources/src_nope/lineage",
            headers=expert_headers,
        )
        assert resp.status_code == 404
