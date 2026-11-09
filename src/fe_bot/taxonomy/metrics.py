"""Taxonomy metrics (SETUP-12 / T-S12-100).

Тонкая обёртка над ``MetricsRegistry`` для трекинга:

- ``taxonomy_classification_total{level, outcome}`` — counter.
  outcomes: ``existing | new | force_merge | class_overflow | unknown``.
- ``taxonomy_new_class_total{level, parent_path}`` — counter авто-
  созданных классов.
- ``taxonomy_force_merge_total{level, parent_path}`` — counter
  force-merge событий (для алёртов).
- ``taxonomy_classification_latency_seconds{level}`` — histogram
  (latency одного LLM-вызова на уровне).
- ``taxonomy_slots_used{level, parent_path}`` — gauge, сколько из 10
  слотов занято на parent_path.
- ``taxonomy_llm_unknown_total{level}`` — counter cascading-unknown
  на каждом уровне.

См. документы:
- docs/tech-debt/TD-HTC-003-drift-alerts.md
"""

from __future__ import annotations

from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.taxonomy.auto_allocator import AllocationSource


class TaxonomyMetrics:
    """Адаптер MetricsRegistry для taxonomy events."""

    def __init__(self, registry: MetricsRegistry) -> None:
        self._reg = registry

    # ------------------------------------------------------------------
    # Classification events
    # ------------------------------------------------------------------

    def classify_existing(self, *, level: int) -> None:
        self._reg.inc(
            "taxonomy_classification_total",
            labels={"level": str(level), "outcome": "existing"},
        )

    def classify_new(self, *, level: int, parent_path: str) -> None:
        self._reg.inc(
            "taxonomy_classification_total",
            labels={"level": str(level), "outcome": "new"},
        )
        self._reg.inc(
            "taxonomy_new_class_total",
            labels={
                "level": str(level),
                "parent_path": parent_path,
            },
        )

    def classify_force_merge(
        self, *, level: int, parent_path: str
    ) -> None:
        self._reg.inc(
            "taxonomy_classification_total",
            labels={"level": str(level), "outcome": "force_merge"},
        )
        self._reg.inc(
            "taxonomy_force_merge_total",
            labels={
                "level": str(level),
                "parent_path": parent_path,
            },
        )

    def classify_overflow(
        self, *, level: int, parent_path: str
    ) -> None:
        # CLASS_OVERFLOW тоже считаем как force_merge_total — обоим
        # видам нужен alert.
        self._reg.inc(
            "taxonomy_classification_total",
            labels={"level": str(level), "outcome": "class_overflow"},
        )
        self._reg.inc(
            "taxonomy_force_merge_total",
            labels={
                "level": str(level),
                "parent_path": parent_path,
            },
        )

    def classify_unknown(self, *, level: int) -> None:
        self._reg.inc(
            "taxonomy_classification_total",
            labels={"level": str(level), "outcome": "unknown"},
        )
        self._reg.inc(
            "taxonomy_llm_unknown_total",
            labels={"level": str(level)},
        )

    # ------------------------------------------------------------------
    # AutoAllocator integration
    # ------------------------------------------------------------------

    def record_allocation(
        self,
        *,
        source: AllocationSource,
        level: int,
        parent_path: str,
    ) -> None:
        """Convenience: маппит AllocationSource → конкретный метод."""
        if source == AllocationSource.AUTO_CREATE:
            self.classify_new(level=level, parent_path=parent_path)
        elif source == AllocationSource.FORCE_MERGE:
            self.classify_force_merge(level=level, parent_path=parent_path)
        elif source == AllocationSource.CLASS_OVERFLOW:
            self.classify_overflow(level=level, parent_path=parent_path)
        # SLUG_MATCH и SIMILARITY_REUSE → existing path (классификация
        # удалась, ничего нового не создалось).
        else:
            self.classify_existing(level=level)

    # ------------------------------------------------------------------
    # Latency
    # ------------------------------------------------------------------

    def observe_latency(self, *, level: int, seconds: float) -> None:
        self._reg.observe(
            "taxonomy_classification_latency_seconds",
            labels={"level": str(level)},
            value=seconds,
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )

    # ------------------------------------------------------------------
    # Slot usage gauges
    # ------------------------------------------------------------------

    def set_slots_used(
        self, *, level: int, parent_path: str, used: int
    ) -> None:
        self._reg.gauge(
            "taxonomy_slots_used",
            labels={
                "level": str(level),
                "parent_path": parent_path,
            },
            value=float(used),
        )


__all__ = ["TaxonomyMetrics"]
