"""Unit tests for ReviewMetricsCollector (SETUP-06 / T-S06-018)."""

from __future__ import annotations

from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_review.metrics import ReviewMetricsCollector


def test_no_op_without_registry():
    c = ReviewMetricsCollector(metrics=None)
    # Should not raise
    c.record_decision(decision="approve")
    c.record_approved(doc_type="schema_card")
    c.observe_duration(decision="approve", doc_type="schema_card", duration_ms=42)


def test_decision_counter():
    m = MetricsRegistry()
    c = ReviewMetricsCollector(metrics=m)
    c.record_decision(decision="approve")
    c.record_decision(decision="approve")
    c.record_decision(decision="reject")
    assert m.counter_value("rag_card_reviews_total", labels={"decision": "approve"}) == 2.0
    assert m.counter_value("rag_card_reviews_total", labels={"decision": "reject"}) == 1.0


def test_approved_counter_per_doc_type():
    m = MetricsRegistry()
    c = ReviewMetricsCollector(metrics=m)
    c.record_approved(doc_type="schema_card")
    c.record_approved(doc_type="task_card")
    assert m.counter_value("rag_card_approved_total", labels={"doc_type": "schema_card"}) == 1.0


def test_rejected_counter_with_reason():
    m = MetricsRegistry()
    c = ReviewMetricsCollector(metrics=m)
    c.record_rejected(doc_type="schema_card", reason="duplicate")
    assert (
        m.counter_value(
            "rag_card_rejected_total",
            labels={"doc_type": "schema_card", "reason": "duplicate"},
        )
        == 1.0
    )


def test_validation_blocked_counter():
    m = MetricsRegistry()
    c = ReviewMetricsCollector(metrics=m)
    c.record_validation_blocked_approve(error_code="SOURCE_TRACE_REQUIRED")
    assert (
        m.counter_value(
            "rag_card_validation_blocked_approve_total",
            labels={"error_code": "SOURCE_TRACE_REQUIRED"},
        )
        == 1.0
    )


def test_version_conflict_counter():
    m = MetricsRegistry()
    c = ReviewMetricsCollector(metrics=m)
    c.record_version_conflict()
    c.record_version_conflict()
    assert m.counter_value("rag_card_version_conflicts_total") == 2.0


def test_duration_histogram():
    m = MetricsRegistry()
    c = ReviewMetricsCollector(metrics=m)
    c.observe_duration(decision="approve", doc_type="schema_card", duration_ms=100)
    c.observe_duration(decision="approve", doc_type="schema_card", duration_ms=200)
    assert (
        m.histogram_count(
            "rag_card_review_duration_ms",
            labels={"decision": "approve", "doc_type": "schema_card"},
        )
        == 2
    )
