"""Unit tests for CardBodyValidator (SETUP-06 / T-S06-013)."""

from __future__ import annotations

from datetime import UTC, datetime

from fe_bot.setup.card_review.validators import CardBodyValidator
from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard


def _card(body: str) -> RAGCard:
    return RAGCard(
        doc_id="schema.x.v1",
        doc_type=DocType.SCHEMA_CARD,
        title="Test",
        version="1.0",
        status=CardStatus.GENERATED,
        body_markdown=body,
        front_matter={},
        source_document_ids=["src_1"],
        source_section_ids=["sec_1"],
        created_by="u1",
        created_at=datetime(2026, 6, 23, tzinfo=UTC),
        updated_at=datetime(2026, 6, 23, tzinfo=UTC),
    )


def test_body_valid():
    v = CardBodyValidator()
    result = v.validate(_card("This is a valid markdown body with enough content."))
    assert result.passed
    assert result.errors == []


def test_body_whitespace_only():
    # Pydantic enforces min_length=1, so "empty" в smysle SETUP-06 — whitespace.
    v = CardBodyValidator()
    result = v.validate(_card("   \n\t  "))
    assert not result.passed
    assert result.errors[0].code == "CARD_BODY_EMPTY"


def test_body_single_char_is_too_short():
    v = CardBodyValidator()
    result = v.validate(_card("x"))
    assert not result.passed
    assert any(e.code == "CARD_BODY_TOO_SHORT" for e in result.errors)


def test_body_too_short():
    v = CardBodyValidator()
    result = v.validate(_card("short"))
    assert not result.passed
    assert any(e.code == "CARD_BODY_TOO_SHORT" for e in result.errors)


def test_body_script_tag_blocked():
    v = CardBodyValidator()
    result = v.validate(_card("# Title\n\n<script>alert(1)</script>\n\nBody"))
    assert not result.passed
    assert any(e.code == "CARD_BODY_DANGEROUS_HTML" for e in result.errors)


def test_body_iframe_blocked():
    v = CardBodyValidator()
    result = v.validate(_card("# Body\n\n<iframe src='evil.com'></iframe>\n\nMore text"))
    assert any(e.code == "CARD_BODY_DANGEROUS_HTML" for e in result.errors)


def test_body_javascript_uri_blocked():
    v = CardBodyValidator()
    result = v.validate(_card("Click [here](javascript:alert(1)) for details"))
    assert any(e.code == "CARD_BODY_DANGEROUS_HTML" for e in result.errors)


def test_body_safe_html_allowed():
    v = CardBodyValidator()
    result = v.validate(_card("# Heading\n\n**bold** and *italic* with normal text content"))
    assert result.passed
