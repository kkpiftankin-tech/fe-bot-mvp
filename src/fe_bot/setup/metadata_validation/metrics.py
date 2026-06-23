"""ValidationMetricsCollector (SETUP-07 / T-S07-007)."""

from __future__ import annotations

from fe_bot.observability.metrics import MetricsRegistry


class ValidationMetricsCollector:
    """Wrapper над MetricsRegistry для validation метрик."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self._metrics = metrics

    def record_run(self, *, outcome: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "validation_runs_total",
            labels={"outcome": outcome},
            help_text="Validation runs by outcome",
        )

    def record_report(self, *, status: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "validation_reports_total",
            labels={"status": status},
            help_text="Validation reports by status",
        )

    def record_issue(self, *, code: str, severity: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "validation_issues_total",
            labels={"code": code, "severity": severity},
            help_text="Validation issues by code and severity",
        )

    def record_status_transition(self, *, target: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "validation_status_transitions_total",
            labels={"target": target},
            help_text="Card status transitions by validation",
        )

    def observe_card_duration(self, *, duration_ms: float) -> None:
        if self._metrics is None:
            return
        self._metrics.observe(
            "validation_card_duration_ms",
            value=duration_ms,
            help_text="Per-card validation duration in ms",
        )

    def observe_run_duration(self, *, duration_ms: float) -> None:
        if self._metrics is None:
            return
        self._metrics.observe(
            "validation_run_duration_ms",
            value=duration_ms,
            help_text="Full run duration in ms",
        )
