"""LLM call statistics collector (OBS-LLM-01).

Лёгкий in-memory aggregator latency для Ollama-вызовов. Используется UI
для отображения ожидаемого времени каждого LLM-обращения (progress bar
на основе running average / p95).

Hook:
    stats.record(model="llama3.2", latency_ms=4500)

Read:
    stats.snapshot() → ModelStats per model + global
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass


_MAX_SAMPLES = 200  # ring buffer per model


@dataclass(frozen=True)
class ModelStats:
    model: str
    count: int
    avg_ms: float
    p50_ms: float
    p95_ms: float
    last_ms: int | None


class LLMStatsCollector:
    """Thread-safe ring-buffer latency stats per model."""

    def __init__(self, max_samples: int = _MAX_SAMPLES) -> None:
        self._samples: dict[str, deque[int]] = {}
        self._max = max_samples
        self._lock = threading.Lock()

    def record(self, *, model: str, latency_ms: int) -> None:
        with self._lock:
            buf = self._samples.setdefault(model, deque(maxlen=self._max))
            buf.append(max(latency_ms, 0))

    def snapshot(self) -> list[ModelStats]:
        with self._lock:
            return [self._stats_for(m, list(buf)) for m, buf in self._samples.items() if buf]

    def for_model(self, model: str) -> ModelStats | None:
        with self._lock:
            buf = self._samples.get(model)
            if not buf:
                return None
            return self._stats_for(model, list(buf))

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()

    @staticmethod
    def _stats_for(model: str, samples: list[int]) -> ModelStats:
        n = len(samples)
        avg = sum(samples) / n
        ordered = sorted(samples)
        p50 = ordered[n // 2]
        p95_idx = max(0, min(n - 1, int(n * 0.95)))
        p95 = ordered[p95_idx]
        return ModelStats(
            model=model,
            count=n,
            avg_ms=round(avg, 1),
            p50_ms=float(p50),
            p95_ms=float(p95),
            last_ms=samples[-1],
        )
