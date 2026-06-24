"""ChunkingMetricsCollector (SETUP-08 / T-S08-004)."""

from __future__ import annotations

from fe_bot.observability.metrics import MetricsRegistry


class ChunkingMetricsCollector:
    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self._metrics = metrics

    def record_run(self, *, outcome: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "chunking_runs_total",
            labels={"outcome": outcome},
            help_text="Chunking runs by outcome",
        )

    def record_chunk(self, *, chunk_type: str) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(
            "chunks_created_total",
            labels={"chunk_type": chunk_type},
            help_text="Created chunks by type",
        )

    def observe_card_duration(self, *, duration_ms: float) -> None:
        if self._metrics is None:
            return
        self._metrics.observe(
            "chunking_card_duration_ms",
            value=duration_ms,
            help_text="Per-card chunking duration in ms",
        )

    def observe_run_duration(self, *, duration_ms: float) -> None:
        if self._metrics is None:
            return
        self._metrics.observe(
            "chunking_run_duration_ms",
            value=duration_ms,
            help_text="Full run duration in ms",
        )
