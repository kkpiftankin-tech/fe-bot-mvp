"""Тесты RAG metadata validator (T-S01-005)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.rag.ontology import (
    ConfidenceLevel,
    DataSource,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata
from schemas.setup.validation_report import (
    ValidationStatus,
    ValidationTargetType,
)
from validators.rag_metadata_validator import (
    VALIDATOR_NAME,
    validate_metadata_only,
    validate_rag_card,
)

pytestmark = pytest.mark.unit


def _make_card(**overrides: object) -> RAGCard:
    defaults: dict[str, object] = {
        "doc_id": "analytics.sensor_analytics_T.v1",
        "doc_type": DocType.ANALYTICS_CARD,
        "title": "Sensor analytics",
        "version": "1.0",
        "status": CardStatus.METADATA_VALIDATED,
        "body_markdown": "# Sensor analytics\n\nBody text.\n",
        "source_document_ids": ["src_001"],
        "created_by": "rag_admin",
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return RAGCard.model_validate(defaults)


def _make_metadata(**overrides: object) -> RAGMetadata:
    defaults: dict[str, object] = {
        "doc_id": "analytics.sensor_analytics_T.v1",
        "doc_type": DocType.ANALYTICS_CARD,
        "phase": [Phase.FEATURE_SYNTHESIS],
        "retrieval_tags": ["sensor analytics", "feature store"],
        "domain": [Domain.NAVAL],
        "data_source": [DataSource.RADAR],
        "task_type": [TaskType.CLASSIFICATION],
        "agent_targets": ["FeatureSynthesisAgent"],
        "confidence_level": ConfidenceLevel.HIGH,
    }
    defaults.update(overrides)
    return RAGMetadata.model_validate(defaults)


class TestValidateRAGCardHappy:
    def test_valid_card_passes(self) -> None:
        report = validate_rag_card(_make_card(), _make_metadata())
        assert report.status == ValidationStatus.PASSED
        assert report.errors == []
        assert report.warnings == []
        assert report.target_type == ValidationTargetType.RAG_CARD
        assert report.validator_name == VALIDATOR_NAME
        assert report.is_passing

    def test_all_checks_recorded(self) -> None:
        report = validate_rag_card(_make_card(), _make_metadata())
        names = {c.name for c in report.checks}
        assert "doc_id_consistency" in names
        assert "doc_type_consistency" in names
        assert "doc_id_uniqueness" in names
        assert "retrieval_tags_nonempty" in names
        assert "body_markdown_nonempty" in names


class TestValidateRAGCardErrors:
    def test_doc_id_mismatch(self) -> None:
        card = _make_card(doc_id="card.doc.v1")
        meta = _make_metadata(doc_id="other.doc.v1")
        report = validate_rag_card(card, meta)
        assert report.status == ValidationStatus.FAILED
        codes = {e.code for e in report.errors}
        assert "DOC_ID_MISMATCH" in codes

    def test_doc_type_mismatch(self) -> None:
        card = _make_card(doc_type=DocType.SCHEMA_CARD)
        meta = _make_metadata(doc_type=DocType.TASK_CARD)
        # Также doc_ids разойдутся? Они одинаковы — оставим только doc_type mismatch
        # для чистого случая.
        # Но card.doc_id и meta.doc_id ==. doc_types отличаются.
        report = validate_rag_card(card, meta)
        codes = {e.code for e in report.errors}
        assert "DOC_TYPE_MISMATCH" in codes
        assert report.status == ValidationStatus.FAILED

    def test_doc_id_duplicate(self) -> None:
        card = _make_card()
        meta = _make_metadata()
        report = validate_rag_card(
            card, meta, known_doc_ids=["analytics.sensor_analytics_T.v1"]
        )
        codes = {e.code for e in report.errors}
        assert "DOC_ID_DUPLICATE" in codes

    def test_empty_body_markdown_caught_at_schema(self) -> None:
        # Empty body отвергается ещё схемой RAGCard, до валидатора.
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            _make_card(body_markdown="")

    def test_whitespace_body_caught_by_validator(self) -> None:
        # Whitespace-only body проходит схему (min_length=1), но валидатор ловит.
        card = _make_card(body_markdown="   \n  ")
        report = validate_rag_card(card, _make_metadata())
        codes = {e.code for e in report.errors}
        assert "BODY_EMPTY" in codes


class TestValidateRAGCardWarnings:
    def test_no_source_documents_is_warning(self) -> None:
        card = _make_card(source_document_ids=[])
        report = validate_rag_card(card, _make_metadata())
        assert report.status == ValidationStatus.WARNING
        codes = {w.code for w in report.warnings}
        assert "NO_SOURCE_DOCUMENTS" in codes

    def test_draft_status_is_warning(self) -> None:
        card = _make_card(status=CardStatus.DRAFT)
        report = validate_rag_card(card, _make_metadata())
        codes = {w.code for w in report.warnings}
        assert "STATUS_NOT_INDEXABLE" in codes

    def test_low_confidence_without_review_is_warning(self) -> None:
        card = _make_card(status=CardStatus.METADATA_VALIDATED)
        meta = _make_metadata(confidence_level=ConfidenceLevel.LOW)
        report = validate_rag_card(card, meta)
        codes = {w.code for w in report.warnings}
        assert "LOW_CONFIDENCE_NEEDS_REVIEW" in codes

    def test_low_confidence_in_review_required_is_ok(self) -> None:
        card = _make_card(status=CardStatus.REVIEW_REQUIRED)
        meta = _make_metadata(confidence_level=ConfidenceLevel.LOW)
        report = validate_rag_card(card, meta)
        codes = {w.code for w in report.warnings}
        assert "LOW_CONFIDENCE_NEEDS_REVIEW" not in codes


class TestRepairInstruction:
    def test_repair_instruction_lists_errors(self) -> None:
        card = _make_card(doc_id="x")
        meta = _make_metadata(doc_id="y")
        report = validate_rag_card(card, meta)
        assert report.repair_instruction is not None
        assert "DOC_ID_MISMATCH" in report.repair_instruction

    def test_no_repair_when_passed(self) -> None:
        report = validate_rag_card(_make_card(), _make_metadata())
        assert report.repair_instruction is None


class TestValidateMetadataOnly:
    def test_valid_metadata_dict_passes(self) -> None:
        report = validate_metadata_only(
            {
                "doc_id": "x.y.v1",
                "doc_type": "schema_card",
                "phase": ["data_profiling"],
                "retrieval_tags": ["t1"],
            }
        )
        assert report.status == ValidationStatus.PASSED

    def test_missing_required_field_schema_error(self) -> None:
        report = validate_metadata_only(
            {
                "doc_type": "schema_card",
                "phase": ["data_profiling"],
                "retrieval_tags": ["t1"],
            }  # no doc_id
        )
        assert report.status == ValidationStatus.FAILED
        assert any(e.code == "SCHEMA_ERROR" for e in report.errors)

    def test_unknown_doc_type_schema_error(self) -> None:
        report = validate_metadata_only(
            {
                "doc_id": "x.v1",
                "doc_type": "garbage_card",
                "phase": ["data_profiling"],
                "retrieval_tags": ["t1"],
            }
        )
        assert report.status == ValidationStatus.FAILED
        assert any(e.code == "SCHEMA_ERROR" for e in report.errors)

    def test_returns_repair_instruction_on_failure(self) -> None:
        report = validate_metadata_only({"doc_id": "x"})
        assert report.repair_instruction is not None
