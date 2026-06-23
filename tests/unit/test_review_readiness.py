"""Unit tests for ReviewReadinessCalculator (SETUP-06 / T-S06-017)."""

from __future__ import annotations

from datetime import UTC, datetime

from fe_bot.setup.card_review.readiness import ReviewReadinessCalculator
from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard


def _card(doc_id: str, status: CardStatus, setup_job_id: str = "sj1") -> RAGCard:
    return RAGCard(
        doc_id=doc_id,
        doc_type=DocType.SCHEMA_CARD,
        title="T",
        version="1.0",
        status=status,
        body_markdown="Some body content here",
        front_matter={},
        source_document_ids=["s1"],
        source_section_ids=["sec1"],
        created_by="u1",
        created_at=datetime(2026, 6, 23, tzinfo=UTC),
        updated_at=datetime(2026, 6, 23, tzinfo=UTC),
        setup_job_id=setup_job_id,
    )


class _Registry:
    def __init__(self, cards: list[RAGCard]) -> None:
        self._cards = cards

    def list_for_setup_job(self, setup_job_id: str) -> list[RAGCard]:
        return [c for c in self._cards if c.setup_job_id == setup_job_id]


def test_empty_setup_not_ready():
    calc = ReviewReadinessCalculator(card_registry=_Registry([]))
    summary = calc.calculate("sj1")
    assert summary.total == 0
    assert summary.ready_for_next_step is False


def test_all_approved_ready():
    registry = _Registry(
        [
            _card("c1", CardStatus.APPROVED),
            _card("c2", CardStatus.APPROVED),
        ]
    )
    calc = ReviewReadinessCalculator(card_registry=registry)
    summary = calc.calculate("sj1")
    assert summary.approved == 2
    assert summary.ready_for_next_step is True


def test_one_review_required_blocks():
    registry = _Registry(
        [
            _card("c1", CardStatus.APPROVED),
            _card("c2", CardStatus.REVIEW_REQUIRED),
        ]
    )
    calc = ReviewReadinessCalculator(card_registry=registry)
    summary = calc.calculate("sj1")
    assert summary.review_required == 1
    assert summary.ready_for_next_step is False


def test_rejected_does_not_block():
    registry = _Registry(
        [
            _card("c1", CardStatus.APPROVED),
            _card("c2", CardStatus.REJECTED),
        ]
    )
    calc = ReviewReadinessCalculator(card_registry=registry)
    summary = calc.calculate("sj1")
    assert summary.rejected == 1
    assert summary.ready_for_next_step is True


def test_validation_failed_blocks():
    registry = _Registry([_card("c1", CardStatus.VALIDATION_FAILED)])
    calc = ReviewReadinessCalculator(card_registry=registry)
    summary = calc.calculate("sj1")
    assert summary.ready_for_next_step is False


def test_ready_for_metadata_validation_counted_as_approved():
    registry = _Registry(
        [
            _card("c1", CardStatus.READY_FOR_METADATA_VALIDATION),
        ]
    )
    calc = ReviewReadinessCalculator(card_registry=registry)
    summary = calc.calculate("sj1")
    assert summary.approved == 1
    assert summary.ready_for_next_step is True


def test_per_status_counts():
    registry = _Registry(
        [
            _card("c1", CardStatus.APPROVED),
            _card("c2", CardStatus.REJECTED),
            _card("c3", CardStatus.REVIEW_REQUIRED),
            _card("c4", CardStatus.LOW_CONFIDENCE),
            _card("c5", CardStatus.EDITED),
            _card("c6", CardStatus.REGENERATE_REQUESTED),
        ]
    )
    calc = ReviewReadinessCalculator(card_registry=registry)
    summary = calc.calculate("sj1")
    assert summary.total == 6
    assert summary.approved == 1
    assert summary.rejected == 1
    assert summary.review_required == 1
    assert summary.low_confidence == 1
    assert summary.edited == 1
    assert summary.regenerate_requested == 1


def test_different_setup_job_isolated():
    registry = _Registry(
        [
            _card("c1", CardStatus.REVIEW_REQUIRED, setup_job_id="sj1"),
            _card("c2", CardStatus.APPROVED, setup_job_id="sj2"),
        ]
    )
    calc = ReviewReadinessCalculator(card_registry=registry)
    assert calc.calculate("sj1").ready_for_next_step is False
    assert calc.calculate("sj2").ready_for_next_step is True
