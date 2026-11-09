"""Unit-тесты TaxonomyMetrics (SETUP-12 / T-S12-100)."""

from __future__ import annotations

import pytest

from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.taxonomy import AllocationSource, TaxonomyMetrics

pytestmark = pytest.mark.unit


def _make() -> tuple[TaxonomyMetrics, MetricsRegistry]:
    reg = MetricsRegistry()
    return TaxonomyMetrics(reg), reg


class TestClassificationCounters:
    def test_existing(self) -> None:
        m, reg = _make()
        m.classify_existing(level=0)
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "0", "outcome": "existing"},
        ) == 1

    def test_new_increments_two_counters(self) -> None:
        m, reg = _make()
        m.classify_new(level=1, parent_path="task")
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "1", "outcome": "new"},
        ) == 1
        assert reg.counter_value(
            "taxonomy_new_class_total",
            labels={"level": "1", "parent_path": "task"},
        ) == 1

    def test_force_merge(self) -> None:
        m, reg = _make()
        m.classify_force_merge(level=1, parent_path="task")
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "1", "outcome": "force_merge"},
        ) == 1
        assert reg.counter_value(
            "taxonomy_force_merge_total",
            labels={"level": "1", "parent_path": "task"},
        ) == 1

    def test_overflow_inflates_force_merge_total(self) -> None:
        # CLASS_OVERFLOW тоже считается в force_merge_total для алёртов.
        m, reg = _make()
        m.classify_overflow(level=2, parent_path="task.pvo")
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "2", "outcome": "class_overflow"},
        ) == 1
        assert reg.counter_value(
            "taxonomy_force_merge_total",
            labels={"level": "2", "parent_path": "task.pvo"},
        ) == 1

    def test_unknown(self) -> None:
        m, reg = _make()
        m.classify_unknown(level=0)
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "0", "outcome": "unknown"},
        ) == 1
        assert reg.counter_value(
            "taxonomy_llm_unknown_total", labels={"level": "0"}
        ) == 1


class TestRecordAllocation:
    def test_auto_create_routes_to_new(self) -> None:
        m, reg = _make()
        m.record_allocation(
            source=AllocationSource.AUTO_CREATE,
            level=1,
            parent_path="task",
        )
        assert reg.counter_value(
            "taxonomy_new_class_total",
            labels={"level": "1", "parent_path": "task"},
        ) == 1

    def test_force_merge_routes_to_force_merge(self) -> None:
        m, reg = _make()
        m.record_allocation(
            source=AllocationSource.FORCE_MERGE,
            level=1,
            parent_path="task",
        )
        assert reg.counter_value(
            "taxonomy_force_merge_total",
            labels={"level": "1", "parent_path": "task"},
        ) == 1

    def test_overflow_routes_to_overflow(self) -> None:
        m, reg = _make()
        m.record_allocation(
            source=AllocationSource.CLASS_OVERFLOW,
            level=1,
            parent_path="task",
        )
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "1", "outcome": "class_overflow"},
        ) == 1

    def test_slug_match_counts_as_existing(self) -> None:
        m, reg = _make()
        m.record_allocation(
            source=AllocationSource.SLUG_MATCH,
            level=0,
            parent_path="",
        )
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "0", "outcome": "existing"},
        ) == 1

    def test_similarity_reuse_counts_as_existing(self) -> None:
        m, reg = _make()
        m.record_allocation(
            source=AllocationSource.SIMILARITY_REUSE,
            level=1,
            parent_path="task",
        )
        assert reg.counter_value(
            "taxonomy_classification_total",
            labels={"level": "1", "outcome": "existing"},
        ) == 1


class TestLatency:
    def test_observe_latency(self) -> None:
        m, reg = _make()
        m.observe_latency(level=0, seconds=2.5)
        m.observe_latency(level=0, seconds=1.5)
        labels = {"level": "0"}
        assert reg.histogram_count(
            "taxonomy_classification_latency_seconds", labels=labels
        ) == 2
        assert reg.histogram_sum(
            "taxonomy_classification_latency_seconds", labels=labels
        ) == pytest.approx(4.0)


class TestSlotsUsedGauge:
    def test_set_and_overwrite(self) -> None:
        m, reg = _make()
        m.set_slots_used(level=0, parent_path="", used=5)
        labels = {"level": "0", "parent_path": ""}
        assert reg.gauge_value("taxonomy_slots_used", labels=labels) == 5.0
        m.set_slots_used(level=0, parent_path="", used=9)
        assert reg.gauge_value("taxonomy_slots_used", labels=labels) == 9.0

    def test_per_parent_path(self) -> None:
        m, reg = _make()
        m.set_slots_used(level=1, parent_path="task", used=4)
        m.set_slots_used(level=1, parent_path="schema", used=2)
        assert reg.gauge_value(
            "taxonomy_slots_used",
            labels={"level": "1", "parent_path": "task"},
        ) == 4.0
        assert reg.gauge_value(
            "taxonomy_slots_used",
            labels={"level": "1", "parent_path": "schema"},
        ) == 2.0
