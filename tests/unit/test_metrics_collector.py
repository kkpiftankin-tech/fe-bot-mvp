"""Тесты Metrics Collector (T-S01-049)."""

from __future__ import annotations

import pytest

from fe_bot.observability.metrics import (
    DEFAULT_BUCKETS,
    MetricsRegistry,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def reg() -> MetricsRegistry:
    return MetricsRegistry()


class TestCounter:
    def test_inc_default_value(self, reg: MetricsRegistry) -> None:
        reg.inc("foo_total", help_text="how many foos")
        reg.inc("foo_total")
        assert reg.counter_value("foo_total") == 2.0

    def test_inc_with_labels(self, reg: MetricsRegistry) -> None:
        reg.inc("jobs_created_total", labels={"role": "user"})
        reg.inc("jobs_created_total", labels={"role": "admin"})
        reg.inc("jobs_created_total", labels={"role": "user"})
        assert reg.counter_value("jobs_created_total", labels={"role": "user"}) == 2.0
        assert reg.counter_value("jobs_created_total", labels={"role": "admin"}) == 1.0

    def test_inc_with_custom_value(self, reg: MetricsRegistry) -> None:
        reg.inc("bytes_uploaded_total", value=1024.0)
        reg.inc("bytes_uploaded_total", value=512.5)
        assert reg.counter_value("bytes_uploaded_total") == 1536.5

    def test_label_order_normalized(self, reg: MetricsRegistry) -> None:
        # b=2, a=1 vs a=1, b=2 → одна series
        reg.inc("x", labels={"b": "2", "a": "1"})
        reg.inc("x", labels={"a": "1", "b": "2"})
        assert reg.counter_value("x", labels={"a": "1", "b": "2"}) == 2.0


class TestHistogram:
    def test_observe_increments_count(self, reg: MetricsRegistry) -> None:
        reg.observe("pipeline_duration_seconds", 0.3)
        reg.observe("pipeline_duration_seconds", 1.5)
        assert reg.histogram_count("pipeline_duration_seconds") == 2
        assert reg.histogram_sum("pipeline_duration_seconds") == 1.8

    def test_observe_with_labels(self, reg: MetricsRegistry) -> None:
        reg.observe("rpc_latency_seconds", 0.05, labels={"op": "embed"})
        reg.observe("rpc_latency_seconds", 0.1, labels={"op": "embed"})
        reg.observe("rpc_latency_seconds", 0.3, labels={"op": "search"})
        assert (
            reg.histogram_count("rpc_latency_seconds", labels={"op": "embed"}) == 2
        )
        assert (
            reg.histogram_sum("rpc_latency_seconds", labels={"op": "search"}) == 0.3
        )

    def test_buckets_default_count(self, reg: MetricsRegistry) -> None:
        reg.observe("x", 0.5)
        text = reg.render_prometheus()
        # 11 default buckets + +Inf
        assert text.count("x_bucket") == len(DEFAULT_BUCKETS) + 1


class TestGauge:
    def test_gauge_set_overwrites(self, reg: MetricsRegistry) -> None:
        reg.gauge("active_jobs", 3.0)
        reg.gauge("active_jobs", 5.0)
        assert reg.gauge_value("active_jobs") == 5.0

    def test_gauge_with_labels(self, reg: MetricsRegistry) -> None:
        reg.gauge("kb_active", 1.0, labels={"setup_job_id": "j1"})
        reg.gauge("kb_active", 0.0, labels={"setup_job_id": "j2"})
        assert reg.gauge_value("kb_active", labels={"setup_job_id": "j1"}) == 1.0
        assert reg.gauge_value("kb_active", labels={"setup_job_id": "j2"}) == 0.0


class TestPrometheusExport:
    def test_export_counter(self, reg: MetricsRegistry) -> None:
        reg.inc("jobs_total", help_text="Total jobs")
        text = reg.render_prometheus()
        assert "# HELP jobs_total Total jobs" in text
        assert "# TYPE jobs_total counter" in text
        assert "jobs_total 1.0" in text

    def test_export_counter_with_labels(self, reg: MetricsRegistry) -> None:
        reg.inc("x", labels={"role": "user"})
        text = reg.render_prometheus()
        assert 'x{role="user"} 1.0' in text

    def test_export_histogram(self, reg: MetricsRegistry) -> None:
        reg.observe("latency", 0.2, help_text="op latency")
        text = reg.render_prometheus()
        assert "# TYPE latency histogram" in text
        assert "latency_sum 0.2" in text
        assert "latency_count 1" in text
        # +Inf bucket с накопленным count
        assert 'le="+Inf"' in text

    def test_export_gauge(self, reg: MetricsRegistry) -> None:
        reg.gauge("queue_depth", 7.0)
        text = reg.render_prometheus()
        assert "# TYPE queue_depth gauge" in text
        assert "queue_depth 7.0" in text

    def test_export_empty_registry(self, reg: MetricsRegistry) -> None:
        assert reg.render_prometheus() == ""


class TestEdgeCases:
    def test_counter_value_unknown_metric(self, reg: MetricsRegistry) -> None:
        assert reg.counter_value("nope") == 0.0

    def test_gauge_value_unknown_returns_none(self, reg: MetricsRegistry) -> None:
        assert reg.gauge_value("nope") is None
