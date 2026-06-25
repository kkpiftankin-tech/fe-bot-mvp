"""Unit tests for LLMStatsCollector (OBS-LLM-01)."""

from __future__ import annotations

from fe_bot.observability.llm_stats import LLMStatsCollector


def test_empty():
    c = LLMStatsCollector()
    assert c.snapshot() == []
    assert c.for_model("llama3.2") is None


def test_record_single():
    c = LLMStatsCollector()
    c.record(model="llama3.2", latency_ms=1500)
    snap = c.snapshot()
    assert len(snap) == 1
    s = snap[0]
    assert s.model == "llama3.2"
    assert s.count == 1
    assert s.avg_ms == 1500.0
    assert s.last_ms == 1500


def test_record_multiple_avg_p95():
    c = LLMStatsCollector()
    for ms in [1000, 2000, 3000, 4000, 5000]:
        c.record(model="llama3.2", latency_ms=ms)
    s = c.for_model("llama3.2")
    assert s is not None
    assert s.count == 5
    assert s.avg_ms == 3000.0
    assert s.p50_ms == 3000.0
    # p95 of 5 sorted values [1000,2000,3000,4000,5000] at idx min(4, int(5*0.95))=4 → 5000
    assert s.p95_ms == 5000.0


def test_per_model():
    c = LLMStatsCollector()
    c.record(model="llama3.2", latency_ms=1000)
    c.record(model="nomic-embed-text", latency_ms=200)
    snap = c.snapshot()
    assert {s.model for s in snap} == {"llama3.2", "nomic-embed-text"}


def test_ring_buffer_caps():
    c = LLMStatsCollector(max_samples=3)
    for ms in [100, 200, 300, 400, 500]:
        c.record(model="m", latency_ms=ms)
    s = c.for_model("m")
    assert s is not None
    # Only last 3 samples: 300, 400, 500
    assert s.count == 3
    assert s.avg_ms == 400.0


def test_negative_clamped():
    c = LLMStatsCollector()
    c.record(model="m", latency_ms=-50)
    s = c.for_model("m")
    assert s is not None
    assert s.last_ms == 0


def test_clear():
    c = LLMStatsCollector()
    c.record(model="m", latency_ms=100)
    c.clear()
    assert c.snapshot() == []
