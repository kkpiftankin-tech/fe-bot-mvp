"""Unit tests for PreApproveValidationOrchestrator (SETUP-06 / T-S06-014)."""

from __future__ import annotations

from datetime import UTC, datetime

from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard

from fe_bot.setup.card_review.validators import PreApproveValidationOrchestrator


def _card(**kw: object) -> RAGCard:
    defaults: dict[str, object] = {
        "doc_id": "schema.x.v1",
        "doc_type": DocType.SCHEMA_CARD,
        "title": "Test",
        "version": "1.0",
        "status": CardStatus.GENERATED,
        "body_markdown": "Some valid body content here with enough length",
        "front_matter": {},
        "source_document_ids": ["src_1"],
        "source_section_ids": ["sec_1"],
        "created_by": "u1",
        "created_at": datetime(2026, 6, 23, tzinfo=UTC),
        "updated_at": datetime(2026, 6, 23, tzinfo=UTC),
        "confidence_level": "high",
    }
    defaults.update(kw)
    return RAGCard(**defaults)  # type: ignore[arg-type]


def test_happy_path_passed():
    o = PreApproveValidationOrchestrator()
    r = o.validate(_card())
    assert r.passed
    assert r.critical_errors == []


def test_no_source_trace_fails():
    o = PreApproveValidationOrchestrator()
    r = o.validate(_card(source_document_ids=[], source_section_ids=[]))
    assert not r.passed
    assert any(e.code == "SOURCE_TRACE_REQUIRED" for e in r.critical_errors)


def test_empty_body_fails():
    o = PreApproveValidationOrchestrator()
    r = o.validate(_card(body_markdown="   "))
    assert not r.passed
    assert any(e.code == "CARD_BODY_EMPTY" for e in r.critical_errors)


def test_low_confidence_warning():
    o = PreApproveValidationOrchestrator()
    r = o.validate(_card(confidence_level="low"))
    assert r.passed  # warnings не блокируют
    assert any(e.code == "LOW_CONFIDENCE_APPROVE" for e in r.warnings)


def test_high_confidence_no_warning():
    o = PreApproveValidationOrchestrator()
    r = o.validate(_card(confidence_level="high"))
    assert r.warnings == []


def test_multiple_critical_errors_collected():
    o = PreApproveValidationOrchestrator()
    r = o.validate(
        _card(
            source_document_ids=[],
            source_section_ids=[],
            body_markdown="   ",
        )
    )
    assert not r.passed
    codes = {e.code for e in r.critical_errors}
    assert "SOURCE_TRACE_REQUIRED" in codes
    assert "CARD_BODY_EMPTY" in codes
