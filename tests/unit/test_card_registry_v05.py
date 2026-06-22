"""Тесты SETUP-05 extension API на InMemoryRAGCardRegistry (T-S05-010).

Новые методы: save_version, get_version, list_versions, latest_version,
save_metadata, get_metadata, attach_artifact, list_artifacts,
list_for_setup_job (с фильтрами), snapshot/restore.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.setup.rag_card_metadata import RAGCardMetadataDTO

from fe_bot.setup.card_registry.service import (
    CardAlreadyExistsError,
    CardNotFoundError,
    InMemoryRAGCardRegistry,
)

pytestmark = pytest.mark.unit


def _card(
    *,
    doc_id: str = "analytics.x.v1",
    card_version: str = "1.0",
    setup_job_id: str = "setup_001",
    doc_type: DocType = DocType.ANALYTICS_CARD,
    status: CardStatus = CardStatus.GENERATED,
    confidence_level: str | None = "high",
    source_document_ids: list[str] | None = None,
) -> RAGCard:
    now = datetime(2026, 6, 19, tzinfo=UTC)
    return RAGCard(
        doc_id=doc_id,
        doc_type=doc_type,
        title="Test card",
        version="1.0",
        status=status,
        body_markdown="# Test\n\nbody",
        source_document_ids=source_document_ids or ["src_001"],
        created_by="rag-card-generator",
        created_at=now,
        updated_at=now,
        setup_job_id=setup_job_id,
        card_version=card_version,
        confidence_level=confidence_level,
    )


def _meta(doc_id: str = "analytics.x.v1", card_version: str = "1.0") -> RAGCardMetadataDTO:
    return RAGCardMetadataDTO(
        doc_id=doc_id,
        card_version=card_version,
        front_matter={"doc_id": doc_id, "version": card_version},
        domain=["naval"],
        phase=["feature_synthesis"],
        retrieval_tags=["test"],
    )


class TestVersioning:
    def test_save_and_get_version(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(card_version="1.0"))
        loaded = reg.get_version("analytics.x.v1", "1.0")
        assert loaded.card_version == "1.0"

    def test_duplicate_version_raises(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(card_version="1.0"))
        with pytest.raises(CardAlreadyExistsError):
            reg.save_version(_card(card_version="1.0"))

    def test_list_versions_ordered(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(card_version="1.0"))
        reg.save_version(_card(card_version="1.1"))
        reg.save_version(_card(card_version="2.0"))
        assert reg.list_versions("analytics.x.v1") == ["1.0", "1.1", "2.0"]

    def test_latest_version(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(card_version="1.0"))
        reg.save_version(_card(card_version="2.0"))
        latest = reg.latest_version("analytics.x.v1")
        assert latest is not None
        assert latest.card_version == "2.0"

    def test_latest_version_missing(self) -> None:
        reg = InMemoryRAGCardRegistry()
        assert reg.latest_version("ghost") is None

    def test_get_unknown_version_raises(self) -> None:
        reg = InMemoryRAGCardRegistry()
        with pytest.raises(CardNotFoundError):
            reg.get_version("analytics.x.v1", "1.0")


class TestMetadata:
    def test_save_and_get_metadata(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_metadata(_meta())
        loaded = reg.get_metadata("analytics.x.v1", "1.0")
        assert loaded.domain == ["naval"]

    def test_save_overwrites_last_write_wins(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_metadata(_meta())
        new_meta = _meta()
        new_meta_dict = new_meta.model_dump()
        new_meta_dict["domain"] = ["industrial"]
        # Re-validate copy с обновлёнными доменами.
        updated = RAGCardMetadataDTO.model_validate(new_meta_dict)
        reg.save_metadata(updated)
        assert reg.get_metadata("analytics.x.v1", "1.0").domain == ["industrial"]

    def test_get_metadata_unknown_raises(self) -> None:
        reg = InMemoryRAGCardRegistry()
        with pytest.raises(CardNotFoundError):
            reg.get_metadata("ghost", "1.0")


class TestArtifacts:
    def test_attach_and_list(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.attach_artifact(
            doc_id="analytics.x.v1",
            card_version="1.0",
            artifact_id="art_md_001",
            artifact_type="markdown",
        )
        reg.attach_artifact(
            doc_id="analytics.x.v1",
            card_version="1.0",
            artifact_id="art_json_001",
            artifact_type="metadata_json",
        )
        artifacts = reg.list_artifacts("analytics.x.v1", "1.0")
        assert ("art_md_001", "markdown") in artifacts
        assert ("art_json_001", "metadata_json") in artifacts


class TestListForSetupJob:
    def test_filter_by_doc_type(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(doc_id="a.v1", doc_type=DocType.ANALYTICS_CARD))
        reg.save_version(_card(doc_id="t.v1", doc_type=DocType.TASK_CARD))
        result = reg.list_for_setup_job("setup_001", doc_type=DocType.ANALYTICS_CARD)
        assert len(result) == 1
        assert result[0].doc_id == "a.v1"

    def test_filter_by_status(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(doc_id="a.v1", status=CardStatus.GENERATED))
        reg.save_version(_card(doc_id="b.v1", status=CardStatus.REVIEW_REQUIRED))
        result = reg.list_for_setup_job("setup_001", status=CardStatus.REVIEW_REQUIRED)
        assert len(result) == 1
        assert result[0].doc_id == "b.v1"

    def test_filter_by_confidence(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(doc_id="a.v1", confidence_level="high"))
        reg.save_version(_card(doc_id="b.v1", confidence_level="low"))
        result = reg.list_for_setup_job("setup_001", confidence_level="low")
        assert len(result) == 1
        assert result[0].doc_id == "b.v1"

    def test_filter_by_source_document_id(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(doc_id="a.v1", source_document_ids=["src_001"]))
        reg.save_version(_card(doc_id="b.v1", source_document_ids=["src_002"]))
        result = reg.list_for_setup_job("setup_001", source_document_id="src_001")
        assert len(result) == 1
        assert result[0].doc_id == "a.v1"

    def test_latest_version_only(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card(doc_id="a.v1", card_version="1.0"))
        reg.save_version(_card(doc_id="a.v1", card_version="2.0"))
        result = reg.list_for_setup_job("setup_001")
        # Только одна карточка (latest = 2.0).
        assert len(result) == 1
        assert result[0].card_version == "2.0"


class TestSnapshotRestore:
    def test_roundtrip_v05_data(self) -> None:
        reg = InMemoryRAGCardRegistry()
        reg.save_version(_card())
        reg.save_metadata(_meta())
        reg.attach_artifact(
            doc_id="analytics.x.v1",
            card_version="1.0",
            artifact_id="art_001",
        )
        snap = reg.snapshot()
        reg2 = InMemoryRAGCardRegistry()
        reg2.restore(snap)
        assert reg2.get_version("analytics.x.v1", "1.0").card_version == "1.0"
        assert reg2.get_metadata("analytics.x.v1", "1.0").domain == ["naval"]
        assert reg2.list_artifacts("analytics.x.v1", "1.0") == [("art_001", "markdown")]
