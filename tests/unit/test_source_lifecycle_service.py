"""Unit-тесты SourceLifecycleService (T-S03-009/010/011)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus
from schemas.setup.source_document_metadata import UpdateSourceMetadataRequest
from schemas.setup.status_history import ChangedByType

from fe_bot.setup.source_registry.lifecycle import (
    InvalidStatusTransitionError,
    SourceDocumentNotFoundError,
    SourceLifecycleService,
    SystemMetadataReadOnlyError,
)
from fe_bot.setup.source_registry.lineage import InMemoryLineageRepository
from fe_bot.setup.source_registry.processing_log import (
    InMemoryProcessingLogRepository,
)
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.setup.source_registry.status_history import (
    InMemoryStatusHistoryRepository,
)

pytestmark = pytest.mark.unit

_VALID_CHECKSUM = "a" * 64


def _make_doc(
    *,
    source_document_id: str = "src_001",
    setup_job_id: str = "setup_001",
    status: SourceDocumentStatus = SourceDocumentStatus.UPLOADED,
    checksum: str = _VALID_CHECKSUM,
) -> SourceDocument:
    return SourceDocument(
        source_document_id=source_document_id,
        setup_job_id=setup_job_id,
        filename="doc.md",
        content_type="text/markdown",
        storage_path=f"s3://x/{source_document_id}",
        size_bytes=100,
        checksum=checksum,
        status=status,
        uploaded_by="user_001",
        uploaded_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def svc() -> SourceLifecycleService:
    registry = InMemorySourceRegistry()
    return SourceLifecycleService(
        registry=registry,
        status_history=InMemoryStatusHistoryRepository(),
        processing_log=InMemoryProcessingLogRepository(),
        lineage=InMemoryLineageRepository(),
    )


@pytest.fixture
def svc_with_doc(svc: SourceLifecycleService) -> SourceLifecycleService:
    svc._registry.add(_make_doc())  # type: ignore[attr-defined]
    return svc


# ============================================================
# T-S03-009: update_status
# ============================================================


class TestUpdateStatus:
    def test_success_changes_status_and_writes_history(
        self, svc_with_doc: SourceLifecycleService
    ) -> None:
        updated = svc_with_doc.update_status(
            source_document_id="src_001",
            new_status=SourceDocumentStatus.REGISTERED,
            event_id="evt_001",
            reason="Document registered",
            changed_by_id="upload-svc",
        )
        assert updated.status == SourceDocumentStatus.REGISTERED
        # History entry recorded.
        history = svc_with_doc._history.list_for_document("src_001")  # type: ignore[attr-defined]
        assert len(history) == 1
        assert history[0].old_status == SourceDocumentStatus.UPLOADED
        assert history[0].new_status == SourceDocumentStatus.REGISTERED

    def test_unknown_document_raises(self, svc: SourceLifecycleService) -> None:
        with pytest.raises(SourceDocumentNotFoundError):
            svc.update_status(
                source_document_id="nope",
                new_status=SourceDocumentStatus.REGISTERED,
                event_id="evt_001",
            )

    def test_invalid_transition_rejected(self, svc_with_doc: SourceLifecycleService) -> None:
        with pytest.raises(InvalidStatusTransitionError):
            svc_with_doc.update_status(
                source_document_id="src_001",
                new_status=SourceDocumentStatus.PUBLISHED,  # UPLOADED → PUBLISHED forbidden
                event_id="evt_001",
            )

    def test_idempotent_by_event_id(self, svc_with_doc: SourceLifecycleService) -> None:
        """Повторный update_status с тем же event_id — no-op."""
        first = svc_with_doc.update_status(
            source_document_id="src_001",
            new_status=SourceDocumentStatus.REGISTERED,
            event_id="evt_001",
        )
        # Повтор с тем же event_id, но другим new_status — игнорируется.
        second = svc_with_doc.update_status(
            source_document_id="src_001",
            new_status=SourceDocumentStatus.PARSING,
            event_id="evt_001",
        )
        assert second.status == first.status == SourceDocumentStatus.REGISTERED
        # И ровно одна запись в history.
        assert len(svc_with_doc._history.list_for_document("src_001")) == 1  # type: ignore[attr-defined]

    def test_same_status_transition_writes_history_for_audit(
        self, svc_with_doc: SourceLifecycleService
    ) -> None:
        """UPLOADED → UPLOADED разрешён (idempotency), history запишется."""
        svc_with_doc.update_status(
            source_document_id="src_001",
            new_status=SourceDocumentStatus.UPLOADED,
            event_id="evt_001",
            reason="Retry of upload notification",
        )
        history = svc_with_doc._history.list_for_document("src_001")  # type: ignore[attr-defined]
        assert len(history) == 1
        assert history[0].old_status == history[0].new_status

    def test_multi_step_lifecycle(self, svc_with_doc: SourceLifecycleService) -> None:
        """Полный путь: UPLOADED → REGISTERED → PARSING → PARSED."""
        for i, (status, evt) in enumerate(
            [
                (SourceDocumentStatus.REGISTERED, "evt_1"),
                (SourceDocumentStatus.PARSING, "evt_2"),
                (SourceDocumentStatus.PARSED, "evt_3"),
            ]
        ):
            svc_with_doc.update_status(
                source_document_id="src_001",
                new_status=status,
                event_id=evt,
                changed_by_id=f"svc_{i}",
            )
        history = svc_with_doc._history.list_for_document("src_001")  # type: ignore[attr-defined]
        assert [h.new_status for h in history] == [
            SourceDocumentStatus.REGISTERED,
            SourceDocumentStatus.PARSING,
            SourceDocumentStatus.PARSED,
        ]
        final_doc = svc_with_doc._registry.get("src_001")  # type: ignore[attr-defined]
        assert final_doc.status == SourceDocumentStatus.PARSED

    def test_changed_by_type_persists(self, svc_with_doc: SourceLifecycleService) -> None:
        svc_with_doc.update_status(
            source_document_id="src_001",
            new_status=SourceDocumentStatus.REGISTERED,
            event_id="evt_001",
            changed_by_type=ChangedByType.USER,
            changed_by_id="user_xyz",
        )
        entry = svc_with_doc._history.list_for_document("src_001")[0]  # type: ignore[attr-defined]
        assert entry.changed_by_type == ChangedByType.USER
        assert entry.changed_by_id == "user_xyz"


# ============================================================
# T-S03-010: append_processing_log + link_artifact + get_lineage
# ============================================================


class TestProcessingLog:
    def test_append_log_persists(self, svc: SourceLifecycleService) -> None:
        entry = svc.append_processing_log(
            source_document_id="src_001",
            setup_job_id="setup_001",
            step=ProcessingLogStep.PARSING,
            message="Started",
            event_id="evt_001",
        )
        assert entry.event_id == "evt_001"
        assert entry.step == ProcessingLogStep.PARSING

    def test_append_log_idempotent(self, svc: SourceLifecycleService) -> None:
        first = svc.append_processing_log(
            source_document_id="src_001",
            setup_job_id="setup_001",
            step=ProcessingLogStep.PARSING,
            message="A",
            event_id="evt_001",
        )
        second = svc.append_processing_log(
            source_document_id="src_001",
            setup_job_id="setup_001",
            step=ProcessingLogStep.PARSING,
            message="B",  # different message
            event_id="evt_001",
        )
        assert second.processing_log_id == first.processing_log_id
        assert second.message == "A"  # original preserved

    def test_append_log_with_error_code(self, svc: SourceLifecycleService) -> None:
        entry = svc.append_processing_log(
            source_document_id="src_001",
            setup_job_id="setup_001",
            step=ProcessingLogStep.PARSING,
            message="Boom",
            event_id="evt_err",
            level=ProcessingLogLevel.ERROR,
            error_code="PARSE_TIMEOUT",
        )
        assert entry.error_code == "PARSE_TIMEOUT"
        assert entry.level == ProcessingLogLevel.ERROR


class TestLinkArtifact:
    def test_link_artifact_creates_relation(self, svc_with_doc: SourceLifecycleService) -> None:
        rel = svc_with_doc.link_artifact(
            source_document_id="src_001",
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_v1",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_link_001",
            created_by_service="rag-card-generator",
        )
        assert rel.target_id == "card_v1"

    def test_link_artifact_dangling_source_raises(self, svc: SourceLifecycleService) -> None:
        """Source должен существовать."""
        with pytest.raises(SourceDocumentNotFoundError):
            svc.link_artifact(
                source_document_id="nope",
                target_type=LineageTargetType.RAG_CARD,
                target_id="card_v1",
                relation_type=LineageRelationType.GENERATED_FROM,
                event_id="evt_001",
                created_by_service="svc",
            )

    def test_link_artifact_idempotent_by_event_id(
        self, svc_with_doc: SourceLifecycleService
    ) -> None:
        first = svc_with_doc.link_artifact(
            source_document_id="src_001",
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_v1",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_001",
            created_by_service="svc",
        )
        second = svc_with_doc.link_artifact(
            source_document_id="src_001",
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_v2",  # different target!
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="evt_001",
            created_by_service="svc",
        )
        # Idempotent — возвращает first.
        assert second.lineage_id == first.lineage_id
        assert second.target_id == "card_v1"


class TestGetLineage:
    def test_get_lineage_empty(self, svc_with_doc: SourceLifecycleService) -> None:
        relations, counters = svc_with_doc.get_lineage("src_001")
        assert relations == []
        assert counters.rag_cards_count == 0  # type: ignore[attr-defined]

    def test_get_lineage_with_counters(self, svc_with_doc: SourceLifecycleService) -> None:
        svc_with_doc.link_artifact(
            source_document_id="src_001",
            target_type=LineageTargetType.RAG_CARD,
            target_id="card_1",
            relation_type=LineageRelationType.GENERATED_FROM,
            event_id="e1",
            created_by_service="svc",
        )
        svc_with_doc.link_artifact(
            source_document_id="src_001",
            target_type=LineageTargetType.PARSED_SECTION,
            target_id="sec_1",
            relation_type=LineageRelationType.PARSED_FROM,
            event_id="e2",
            created_by_service="svc",
        )
        relations, counters = svc_with_doc.get_lineage("src_001")
        assert len(relations) == 2
        assert counters.rag_cards_count == 1  # type: ignore[attr-defined]
        assert counters.parsed_sections_count == 1  # type: ignore[attr-defined]

    def test_get_lineage_unknown_source_raises(self, svc: SourceLifecycleService) -> None:
        with pytest.raises(SourceDocumentNotFoundError):
            svc.get_lineage("nope")


# ============================================================
# T-S03-011: update_user_metadata
# ============================================================


class TestUpdateUserMetadata:
    def test_full_patch(self, svc_with_doc: SourceLifecycleService) -> None:
        updated = svc_with_doc.update_user_metadata(
            source_document_id="src_001",
            patch=UpdateSourceMetadataRequest(
                tags=["naval", "schema"],
                description="Тестовое описание",
                owner_note="Проверил",
                custom_labels={"prio": "high"},
            ),
            updated_by="user_001",
        )
        assert updated.metadata["user"]["tags"] == ["naval", "schema"]
        assert updated.metadata["user"]["description"] == "Тестовое описание"
        assert updated.metadata["user"]["custom_labels"] == {"prio": "high"}

    def test_partial_patch_preserves_others(self, svc_with_doc: SourceLifecycleService) -> None:
        svc_with_doc.update_user_metadata(
            source_document_id="src_001",
            patch=UpdateSourceMetadataRequest(
                tags=["initial"],
                description="initial desc",
            ),
            updated_by="user_001",
        )
        # Только tags обновляем — description должен сохраниться.
        updated = svc_with_doc.update_user_metadata(
            source_document_id="src_001",
            patch=UpdateSourceMetadataRequest(tags=["new"]),
            updated_by="user_001",
        )
        assert updated.metadata["user"]["tags"] == ["new"]
        assert updated.metadata["user"]["description"] == "initial desc"

    def test_unknown_document_raises(self, svc: SourceLifecycleService) -> None:
        with pytest.raises(SourceDocumentNotFoundError):
            svc.update_user_metadata(
                source_document_id="nope",
                patch=UpdateSourceMetadataRequest(tags=["x"]),
                updated_by="user_001",
            )

    def test_writes_processing_log_audit(self, svc_with_doc: SourceLifecycleService) -> None:
        svc_with_doc.update_user_metadata(
            source_document_id="src_001",
            patch=UpdateSourceMetadataRequest(tags=["x"]),
            updated_by="user_xyz",
        )
        logs = svc_with_doc._log.list_for_document(  # type: ignore[attr-defined]
            "src_001", step=ProcessingLogStep.METADATA_EXTRACTION
        )
        assert len(logs) == 1
        assert "user_xyz" in logs[0].message

    def test_protected_field_in_dict_rejected(self, svc_with_doc: SourceLifecycleService) -> None:
        """Прямой вызов с patch_dict содержащим protected — на нашем уровне
        Pydantic уже их фильтрует через extra='forbid', но если caller
        обходит схему, защита остаётся."""
        # Создаём напрямую невалидный dict (моделируем misuse).
        # UpdateSourceMetadataRequest.model_dump не даст добавить лишнее,
        # но reject_protected_fields это double-check.
        # Этот тест в основном фиксирует, что Pydantic-уровень работает.
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            UpdateSourceMetadataRequest(
                tags=[],
                checksum="evil",  # type: ignore[call-arg]
            )

    def test_xss_sanitized_via_schema(self, svc_with_doc: SourceLifecycleService) -> None:
        updated = svc_with_doc.update_user_metadata(
            source_document_id="src_001",
            patch=UpdateSourceMetadataRequest(
                description="<script>alert(1)</script>",
            ),
            updated_by="user_001",
        )
        desc = updated.metadata["user"]["description"]
        assert "<script>" not in desc
        assert "&lt;" in desc

    def test_event_id_override(self, svc_with_doc: SourceLifecycleService) -> None:
        """Custom event_id для idempotency-protected log entry."""
        svc_with_doc.update_user_metadata(
            source_document_id="src_001",
            patch=UpdateSourceMetadataRequest(tags=["x"]),
            updated_by="user_001",
            event_id="evt_meta_custom",
        )
        log = svc_with_doc._log.get_by_event_id("evt_meta_custom")  # type: ignore[attr-defined]
        assert log is not None
        # Тот же event_id — second call игнорируется (log не пишется заново).
        svc_with_doc.update_user_metadata(
            source_document_id="src_001",
            patch=UpdateSourceMetadataRequest(tags=["y"]),
            updated_by="user_001",
            event_id="evt_meta_custom",
        )
        logs = svc_with_doc._log.list_for_document(  # type: ignore[attr-defined]
            "src_001", step=ProcessingLogStep.METADATA_EXTRACTION
        )
        # Только один log entry с этим event_id (второй раз — idempotent).
        assert len(logs) == 1


class TestSystemMetadataReadOnlyErrorIntegration:
    """Защита от прямого вызова с protected fields."""

    def test_error_is_reexported(self) -> None:
        # Проверяем что SystemMetadataReadOnlyError доступен из lifecycle.
        assert issubclass(SystemMetadataReadOnlyError, ValueError)
