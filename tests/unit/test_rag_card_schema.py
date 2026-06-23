"""Тесты ParsedSection / RAGCard / RAGMetadata (T-S01-003)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.rag.ontology import (
    ConfidenceLevel,
    DataSource,
    DocType,
    Domain,
    Phase,
    TaskType,
)
from schemas.rag.rag_card import (
    CardStatus,
    InvalidCardTransitionError,
    RAGCard,
)
from schemas.rag.rag_metadata import RAGMetadata
from schemas.setup.parsed_section import ParsedSection, SectionType

pytestmark = pytest.mark.unit


# ---------------- ParsedSection ----------------


def _make_section(**overrides: object) -> ParsedSection:
    defaults: dict[str, object] = {
        "section_id": "sec_001",
        "source_document_id": "src_001",
        "setup_job_id": "setup_001",
        "title": "Threat Evaluation",
        "raw_text": "Some raw text",
        "normalized_text": "some raw text",
        "confidence": 0.9,
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return ParsedSection.model_validate(defaults)


class TestParsedSection:
    def test_valid_section(self) -> None:
        sec = _make_section()
        assert sec.section_type == SectionType.OTHER
        assert sec.confidence == 0.9

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            _make_section(confidence=1.5)
        with pytest.raises(ValidationError):
            _make_section(confidence=-0.1)

    def test_end_offset_must_be_ge_start(self) -> None:
        with pytest.raises(ValidationError):
            _make_section(start_offset=100, end_offset=50)

    def test_offsets_both_optional(self) -> None:
        sec = _make_section(start_offset=None, end_offset=None)
        assert sec.start_offset is None

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_section(raw_text="")
        with pytest.raises(ValidationError):
            _make_section(normalized_text="")


# ---------------- RAGMetadata ----------------


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


class TestRAGMetadata:
    def test_valid_metadata(self) -> None:
        m = _make_metadata()
        assert m.doc_type == DocType.ANALYTICS_CARD
        assert Domain.NAVAL in m.domain

    def test_doc_type_must_be_in_ontology(self) -> None:
        with pytest.raises(ValidationError):
            _make_metadata(doc_type="garbage_card")

    def test_phase_required(self) -> None:
        with pytest.raises(ValidationError):
            _make_metadata(phase=[])

    def test_retrieval_tags_required(self) -> None:
        with pytest.raises(ValidationError):
            _make_metadata(retrieval_tags=[])

    def test_retrieval_tags_no_empty_strings(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _make_metadata(retrieval_tags=["valid", "   "])
        assert "empty strings" in str(exc.value)

    def test_unknown_agent_target_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            _make_metadata(agent_targets=["NonexistentAgent"])
        assert "Unknown agent_targets" in str(exc.value)

    def test_known_agents_accepted(self) -> None:
        m = _make_metadata(
            agent_targets=["NLUAgent", "FeatureSynthesisAgent", "ModelSelectionAgent"]
        )
        assert len(m.agent_targets) == 3

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            RAGMetadata.model_validate(
                {
                    "doc_id": "x",
                    "doc_type": DocType.SCHEMA_CARD,
                    "phase": [Phase.DATA_PROFILING],
                    "retrieval_tags": ["t"],
                    "unexpected": 1,
                }
            )


# ---------------- RAGCard ----------------


def _make_card(**overrides: object) -> RAGCard:
    defaults: dict[str, object] = {
        "doc_id": "schema.tracks_fused.v1",
        "doc_type": DocType.SCHEMA_CARD,
        "title": "Tracks Fused schema",
        "version": "1.0",
        "body_markdown": "# Tracks Fused\n\nSchema definition.\n",
        "created_by": "rag_admin",
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return RAGCard.model_validate(defaults)


class TestRAGCard:
    def test_minimal_valid_card(self) -> None:
        card = _make_card()
        assert card.status == CardStatus.DRAFT
        assert card.version == "1.0"

    def test_all_card_statuses(self) -> None:
        # 10 legacy + 6 SETUP-05 + 4 SETUP-06 lifecycle statuses
        # (см. docs/06-rag/card-lifecycle.md).
        assert {s.value for s in CardStatus} == {
            "draft",
            "generated",
            "metadata_validated",
            "review_required",
            "approved",
            "chunked",
            "embedded",
            "indexed",
            "published",
            "deprecated",
            "generation_failed",
            "metadata_incomplete",
            "body_empty",
            "low_confidence",
            "ready_for_metadata_validation",
            "rejected",
            # SETUP-06:
            "editing",
            "edited",
            "regenerate_requested",
            "validation_failed",
        }

    def test_version_format(self) -> None:
        assert _make_card(version="1").version == "1"
        assert _make_card(version="1.2").version == "1.2"
        assert _make_card(version="2.0.1").version == "2.0.1"
        with pytest.raises(ValidationError):
            _make_card(version="v1")
        with pytest.raises(ValidationError):
            _make_card(version="1.2.3.4")

    def test_full_lifecycle_transitions(self) -> None:
        path = [
            CardStatus.GENERATED,
            CardStatus.METADATA_VALIDATED,
            CardStatus.APPROVED,
            CardStatus.CHUNKED,
            CardStatus.EMBEDDED,
            CardStatus.INDEXED,
            CardStatus.PUBLISHED,
        ]
        card = _make_card()
        for step in path:
            card.transition_to(step)
        assert card.status == CardStatus.PUBLISHED

    def test_published_can_only_deprecate(self) -> None:
        card = _make_card(status=CardStatus.PUBLISHED)
        with pytest.raises(InvalidCardTransitionError):
            card.transition_to(CardStatus.DRAFT)
        card.transition_to(CardStatus.DEPRECATED)
        assert card.status == CardStatus.DEPRECATED

    def test_deprecated_terminal(self) -> None:
        card = _make_card(status=CardStatus.DEPRECATED)
        for target in CardStatus:
            with pytest.raises(InvalidCardTransitionError):
                card.transition_to(target)

    def test_to_markdown_round_trip(self) -> None:
        card = _make_card(
            front_matter={
                "doc_id": "schema.tracks_fused.v1",
                "doc_type": "schema_card",
                "version": "1.0",
            },
            body_markdown="# Tracks Fused\n\nBody text.\n",
        )
        md = card.to_markdown()
        assert md.startswith("---\n")
        assert "doc_id: schema.tracks_fused.v1" in md
        assert "# Tracks Fused" in md

        fm, body = RAGCard.parse_front_matter(md)
        assert fm["doc_id"] == "schema.tracks_fused.v1"
        assert body.startswith("# Tracks Fused")

    def test_parse_front_matter_no_delimiter(self) -> None:
        fm, body = RAGCard.parse_front_matter("Just markdown content")
        assert fm == {}
        assert body == "Just markdown content"

    def test_parse_front_matter_malformed(self) -> None:
        with pytest.raises(ValueError, match="Malformed YAML"):
            RAGCard.parse_front_matter("---\nincomplete front matter")
