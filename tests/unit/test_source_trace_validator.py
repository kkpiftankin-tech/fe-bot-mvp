"""Unit tests for CardSourceTraceValidator (SETUP-06 / T-S06-012)."""

from __future__ import annotations

from datetime import UTC, datetime

from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard

from fe_bot.setup.card_review.validators import CardSourceTraceValidator


def _card(
    *,
    source_documents: list[str] | None = None,
    source_sections: list[str] | None = None,
) -> RAGCard:
    return RAGCard(
        doc_id="schema.x.v1",
        doc_type=DocType.SCHEMA_CARD,
        title="Test",
        version="1.0",
        status=CardStatus.GENERATED,
        body_markdown="Some valid body content here",
        front_matter={},
        source_document_ids=source_documents or [],
        source_section_ids=source_sections or [],
        created_by="u1",
        created_at=datetime(2026, 6, 23, tzinfo=UTC),
        updated_at=datetime(2026, 6, 23, tzinfo=UTC),
    )


class _StubRegistry:
    def __init__(self, known_ids: set[str]) -> None:
        self._known = known_ids

    def exists(self, doc_id: str) -> bool:
        return doc_id in self._known


def test_source_trace_present():
    v = CardSourceTraceValidator()
    result = v.validate(_card(source_documents=["src_1"], source_sections=["sec_1"]))
    assert result.passed


def test_source_trace_missing_both():
    v = CardSourceTraceValidator()
    result = v.validate(_card())
    assert not result.passed
    assert result.errors[0].code == "SOURCE_TRACE_REQUIRED"


def test_only_documents_ok():
    v = CardSourceTraceValidator()
    result = v.validate(_card(source_documents=["src_1"]))
    assert result.passed


def test_only_sections_ok():
    v = CardSourceTraceValidator()
    result = v.validate(_card(source_sections=["sec_1"]))
    assert result.passed


def test_document_not_found():
    registry = _StubRegistry({"src_known"})
    v = CardSourceTraceValidator(source_registry=registry)
    result = v.validate(_card(source_documents=["src_unknown"], source_sections=["sec_1"]))
    assert not result.passed
    assert any(e.code == "SOURCE_DOCUMENT_NOT_FOUND" for e in result.errors)


def test_section_not_found():
    section_repo = _StubRegistry({"sec_known"})
    v = CardSourceTraceValidator(parsed_section_repo=section_repo)
    result = v.validate(_card(source_documents=["src_1"], source_sections=["sec_missing"]))
    assert not result.passed
    assert any(e.code == "SOURCE_SECTION_NOT_FOUND" for e in result.errors)


def test_both_validators_no_errors():
    src = _StubRegistry({"src_1"})
    sec = _StubRegistry({"sec_1"})
    v = CardSourceTraceValidator(source_registry=src, parsed_section_repo=sec)
    result = v.validate(_card(source_documents=["src_1"], source_sections=["sec_1"]))
    assert result.passed
