"""ReviewMetricsCollector (SETUP-06 / T-S06-018).

Тонкая обёртка над MetricsRegistry — emits counters/histograms из
spec §17 (Наблюдаемость).

Counters:
- ``rag_card_reviews_total{decision}`` — все review decisions.
- ``rag_card_approved_total{doc_type}`` — approved cards by type.
- ``rag_card_rejected_total{reason}`` — rejected with reason.
- ``rag_card_edited_total{doc_type}`` — manual edits.
- ``rag_card_regenerate_requested_total{doc_type}``.
- ``rag_card_validation_blocked_approve_total{error_code}`` — approve
  заблокирован validation.
- ``rag_card_version_conflicts_total`` — edit version conflicts.

Histogram:
- ``rag_card_review_duration_ms{decision,doc_type}``.
"""

from __future__ import annotations

from fe_bot.observability.metrics import MetricsRegistry


class ReviewMetricsCollector:
    """Wrapper над MetricsRegistry для review-метрик."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self._metrics = metrics

    def record_decision(self, *, decision: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "rag_card_reviews_total",
            labels={"decision": decision},
            help_text="Total RAG card review decisions",
        )

    def record_approved(self, *, doc_type: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "rag_card_approved_total",
            labels={"doc_type": doc_type},
            help_text="Approved RAG cards by doc_type",
        )

    def record_rejected(self, *, doc_type: str, reason: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "rag_card_rejected_total",
            labels={"doc_type": doc_type, "reason": reason},
            help_text="Rejected RAG cards by reason",
        )

    def record_edited(self, *, doc_type: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "rag_card_edited_total",
            labels={"doc_type": doc_type},
            help_text="Edited RAG cards by doc_type",
        )

    def record_regenerate_requested(self, *, doc_type: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "rag_card_regenerate_requested_total",
            labels={"doc_type": doc_type},
            help_text="Regeneration requests by doc_type",
        )

    def record_validation_blocked_approve(self, *, error_code: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "rag_card_validation_blocked_approve_total",
            labels={"error_code": error_code},
            help_text="Approve blocked by validation by error code",
        )

    def record_version_conflict(self) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "rag_card_version_conflicts_total",
            help_text="Edit version conflicts",
        )

    def observe_duration(
        self,
        *,
        decision: str,
        doc_type: str,
        duration_ms: float,
    ) -> None:
        if self._metrics is None:
            return
        self._metrics.observe(
            "rag_card_review_duration_ms",
            value=duration_ms,
            labels={"decision": decision, "doc_type": doc_type},
            help_text="Review decision duration in ms",
        )
