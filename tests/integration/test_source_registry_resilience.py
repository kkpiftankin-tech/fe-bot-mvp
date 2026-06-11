"""Resilience tests для Source Registry (T-S03-027).

Покрытие: state machine boundaries, idempotency under retry, atomicity на
сбое registry update, cross-job protection, XSS защита, dangling lineage,
concurrent updates, published-блокировка DELETE.

Каждый scenario документирует expected behavior при abnormal input/timing —
бэкап для AC из §18 и §22.1 спека.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep
from schemas.setup.source_document import SourceDocumentStatus

from fe_bot.setup.source_registry.lifecycle import (
    InvalidStatusTransitionError,
)

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    return client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Resilience KB"},
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
# 1. Invalid status transitions (state machine boundaries)
# ============================================================


class TestInvalidStatusTransitions:
    """5 разных недопустимых переходов из §12 спека."""

    def test_uploaded_to_published_rejected(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        # После upload status уже REGISTERED — try jump to PUBLISHED.
        with pytest.raises(InvalidStatusTransitionError):
            _lifecycle(app_with_clean_state).update_status(
                source_document_id=doc_id,
                new_status=SourceDocumentStatus.PUBLISHED,
                event_id="evt_bad",
            )

    def test_registered_to_parsed_rejected(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """REGISTERED → PARSED недопустим (нужен промежуточный PARSING)."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        with pytest.raises(InvalidStatusTransitionError):
            _lifecycle(app_with_clean_state).update_status(
                source_document_id=doc_id,
                new_status=SourceDocumentStatus.PARSED,
                event_id="evt_bad",
            )

    def test_terminal_deprecated_no_outgoing(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        # Force into PUBLISHED through валидную цепочку, потом deprecated.
        svc = _lifecycle(app_with_clean_state)
        chain = [
            SourceDocumentStatus.PARSING,
            SourceDocumentStatus.PARSED,
            SourceDocumentStatus.RAG_CARDS_GENERATING,
            SourceDocumentStatus.RAG_CARDS_GENERATED,
            SourceDocumentStatus.READY_FOR_INDEXING,
            SourceDocumentStatus.PUBLISHED,
            SourceDocumentStatus.DEPRECATED,
        ]
        for i, s in enumerate(chain):
            svc.update_status(
                source_document_id=doc_id,
                new_status=s,
                event_id=f"evt_chain_{i}",
            )
        # DEPRECATED — terminal. Любой следующий переход запрещён.
        with pytest.raises(InvalidStatusTransitionError):
            svc.update_status(
                source_document_id=doc_id,
                new_status=SourceDocumentStatus.PUBLISHED,
                event_id="evt_revive",
            )

    def test_removed_cannot_be_restored(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        # Now REMOVED — terminal.
        with pytest.raises(InvalidStatusTransitionError):
            _lifecycle(app_with_clean_state).update_status(
                source_document_id=doc_id,
                new_status=SourceDocumentStatus.PARSING,
                event_id="evt_restore",
            )

    def test_processing_failed_to_published_rejected(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Из failed нельзя сразу в published."""
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        svc = _lifecycle(app_with_clean_state)
        svc.update_status(
            source_document_id=doc_id,
            new_status=SourceDocumentStatus.PROCESSING_FAILED,
            event_id="evt_fail",
        )
        with pytest.raises(InvalidStatusTransitionError):
            svc.update_status(
                source_document_id=doc_id,
                new_status=SourceDocumentStatus.PUBLISHED,
                event_id="evt_jump",
            )


# ============================================================
# 2. Idempotency under retry
# ============================================================


class TestIdempotencyUnderRetry:
    def test_status_update_same_event_id_is_noop(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        svc = _lifecycle(app_with_clean_state)
        first = svc.update_status(
            source_document_id=doc_id,
            new_status=SourceDocumentStatus.PARSING,
            event_id="evt_retry",
        )
        # Повтор с тем же event_id, другим new_status — idempotent.
        second = svc.update_status(
            source_document_id=doc_id,
            new_status=SourceDocumentStatus.PARSE_FAILED,  # different!
            event_id="evt_retry",
        )
        assert second.status == first.status == SourceDocumentStatus.PARSING

    def test_lineage_link_same_event_id_no_double_publish(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Покрытие T-S03-020 idempotent guard в link_artifact."""
        from fe_bot.api.dependencies import get_event_bus

        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        svc = _lifecycle(app_with_clean_state)
        for _ in range(3):
            svc.link_artifact(
                source_document_id=doc_id,
                target_type=LineageTargetType.RAG_CARD,
                target_id="card_x",
                relation_type=LineageRelationType.GENERATED_FROM,
                event_id="evt_link_same",
                created_by_service="gen",
            )
        bus = app_with_clean_state.dependency_overrides[get_event_bus]()
        link_events = [
            e
            for e in bus.history()
            if e.event_type == "source.document.lineage_updated"
        ]
        assert len(link_events) == 1


# ============================================================
# 3. Cross-job protection
# ============================================================


class TestCrossJobProtection:
    def test_get_details_other_job_returns_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid1 = _create_job(client, auth_headers)
        sid2 = _create_job(client, auth_headers)
        doc_id = _upload(client, sid1, auth_headers)
        resp = client.get(
            f"/api/v1/setup/{sid2}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_patch_metadata_other_job_returns_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        sid1 = _create_job(client, auth_headers)
        sid2 = _create_job(client, auth_headers)
        doc_id = _upload(client, sid1, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid2}/sources/{doc_id}/metadata",
            json={"tags": ["x"]},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ============================================================
# 4. XSS / sanitization
# ============================================================


class TestXSSSanitization:
    def test_xss_in_description_is_escaped(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={
                "description": (
                    '<img src=x onerror=alert(1)><script>console.log(1)</script>'
                )
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        desc = resp.json()["user_metadata"]["description"]
        assert "<script>" not in desc
        assert "<img" not in desc
        assert "&lt;" in desc

    def test_xss_in_tag_is_escaped(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        resp = client.patch(
            f"/api/v1/setup/{sid}/sources/{doc_id}/metadata",
            json={"tags": ['<svg onload="alert(1)">']},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        tag = resp.json()["user_metadata"]["tags"][0]
        assert "<svg" not in tag
        assert "&lt;" in tag


# ============================================================
# 5. Dangling lineage (target non-existent)
# ============================================================


class TestDanglingLineage:
    def test_lineage_with_nonexistent_source_raises(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Source должен существовать для lineage relation."""
        from fe_bot.setup.source_registry.service import (
            SourceDocumentNotFoundError,
        )

        with pytest.raises(SourceDocumentNotFoundError):
            _lifecycle(app_with_clean_state).link_artifact(
                source_document_id="src_nope",
                target_type=LineageTargetType.RAG_CARD,
                target_id="card_x",
                relation_type=LineageRelationType.GENERATED_FROM,
                event_id="evt_dangling",
                created_by_service="gen",
            )

    def test_lineage_with_nonexistent_target_succeeds_in_mvp(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """MVP: target validation отложена (downstream сервисы появятся в SETUP-04+).

        Документирует current scope: можем link'нуть на любой target_id,
        cross-service consistency check добавится позже.
        """
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        rel = _lifecycle(app_with_clean_state).link_artifact(
            source_document_id=doc_id,
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_ghost",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_ghost",
            created_by_service="gen",
        )
        assert rel.target_id == "card_ghost"


# ============================================================
# 6. Published-блокировка DELETE
# ============================================================


class TestPublishedDeleteBlocked:
    def test_user_cannot_delete_published(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        # Force to PUBLISHED.
        from fe_bot.api.dependencies import get_source_registry

        registry = app_with_clean_state.dependency_overrides[
            get_source_registry
        ]()
        doc = registry.get(doc_id)
        registry._by_id[doc_id] = doc.model_copy(  # type: ignore[attr-defined]
            update={"status": SourceDocumentStatus.PUBLISHED}
        )

        resp = client.delete(
            f"/api/v1/setup/{sid}/sources/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "DOCUMENT_ALREADY_PUBLISHED"


# ============================================================
# 7. Concurrent processing failures don't duplicate metrics
# ============================================================


class TestConcurrentFailuresIdempotent:
    def test_same_event_id_does_not_double_metric(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_metrics

        sid = _create_job(client, auth_headers)
        doc_id = _upload(client, sid, auth_headers)
        svc = _lifecycle(app_with_clean_state)
        for _ in range(3):
            svc.append_processing_log(
                source_document_id=doc_id,
                setup_job_id=sid,
                step=ProcessingLogStep.PARSING,
                message="boom",
                event_id="evt_err_same",
                level=ProcessingLogLevel.ERROR,
                error_code="PARSE_TIMEOUT",
            )
        m = app_with_clean_state.dependency_overrides[get_metrics]()
        # Only one error counted (idempotent by event_id).
        assert (
            m.counter_value(
                "source_processing_failures_total",
                labels={"step": "parsing", "error_code": "PARSE_TIMEOUT"},
            )
            == 1.0
        )


# ============================================================
# 8. Retry idempotency
# ============================================================


class TestRetryIdempotency:
    def test_retry_same_event_id_does_not_duplicate(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_audit_log
        from fe_bot.audit.service import AuditAction

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

        for _ in range(3):
            client.post(
                f"/api/v1/setup/{sid}/sources/{doc_id}/retry?event_id=retry_same",
                headers=auth_headers,
            )
        log = app_with_clean_state.dependency_overrides[get_audit_log]()
        retry_events = [
            e
            for e in log.list_for_job(sid)
            if e.action == AuditAction.PROCESSING_RETRY_TRIGGERED
        ]
        # Один audit event (через update_status idempotency).
        assert len(retry_events) <= 1


# ============================================================
# 9. Storage error пропагируется (atomicity)
# ============================================================


class TestStorageFailureDoesNotCorruptHistory:
    def test_upload_storage_failure_does_not_write_registered_history(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Storage upload падает ДО registry.add — никаких lifecycle hooks.

        Гарантирует: в status history нет запись для документа, которого нет
        в registry.
        """
        from fe_bot.api.dependencies import (
            get_artifact_storage,
            get_status_history_repo,
        )
        from fe_bot.storage.artifact_service import StorageUnavailableError

        sid = _create_job(client, auth_headers)
        storage = app_with_clean_state.dependency_overrides[
            get_artifact_storage
        ]()
        with patch.object(
            storage, "upload", side_effect=StorageUnavailableError("S3 down")
        ):
            resp = client.post(
                f"/api/v1/setup/{sid}/documents",
                files={"files": ("fail.md", b"x", "text/markdown")},
                headers=auth_headers,
            )
            assert resp.status_code >= 500

        history = app_with_clean_state.dependency_overrides[
            get_status_history_repo
        ]()
        # Никаких history записей не написано (registry.add не выполнился).
        # Документа в registry нет, так что history тоже пуст.
        assert history._by_document == {}  # type: ignore[attr-defined]
