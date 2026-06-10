"""Metrics Collector (T-S01-049).

In-memory Counter / Histogram / Gauge с экспортом в текстовый Prometheus
формат. В продакшене заменяется на `prometheus_client` без изменений
зависимых сервисов (Protocol-совместимый интерфейс).

Гарантии:
- Thread-safe: все мутации защищены `threading.Lock`.
- Метки (labels) — отсортированный кортеж пар, чтобы один и тот же набор
  labels всегда давал одну series.
- Гистограмма хранит counts по бакетам + sum + count для p50/p99 вычислений
  на стороне сборщика.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass, field

# Дефолтные бакеты для гистограмм latency (секунды).
DEFAULT_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)

# Тип label key/values.
Labels = tuple[tuple[str, str], ...]


def _normalize_labels(labels: dict[str, str] | None) -> Labels:
    if not labels:
        return ()
    return tuple(sorted((k, str(v)) for k, v in labels.items()))


def _format_labels(labels: Labels) -> str:
    if not labels:
        return ""
    items = ",".join(f'{k}="{v}"' for k, v in labels)
    return f"{{{items}}}"


@dataclass(slots=True)
class _CounterState:
    values: dict[Labels, float] = field(default_factory=dict)

    def inc(self, labels: Labels, value: float = 1.0) -> None:
        self.values[labels] = self.values.get(labels, 0.0) + value


@dataclass(slots=True)
class _HistogramState:
    buckets: tuple[float, ...]
    # labels -> {bucket_upper: count}; "+Inf" virtualized как None
    bucket_counts: dict[Labels, list[int]] = field(default_factory=dict)
    sums: dict[Labels, float] = field(default_factory=dict)
    counts: dict[Labels, int] = field(default_factory=dict)

    def observe(self, labels: Labels, value: float) -> None:
        counts = self.bucket_counts.setdefault(
            labels, [0] * (len(self.buckets) + 1)
        )
        for i, upper in enumerate(self.buckets):
            if value <= upper:
                counts[i] += 1
        counts[-1] += 1  # +Inf bucket
        self.sums[labels] = self.sums.get(labels, 0.0) + value
        self.counts[labels] = self.counts.get(labels, 0) + 1


@dataclass(slots=True)
class _GaugeState:
    values: dict[Labels, float] = field(default_factory=dict)

    def set(self, labels: Labels, value: float) -> None:
        self.values[labels] = value


class MetricsRegistry:
    """Реестр метрик — Counter / Histogram / Gauge с экспортом в Prometheus."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, tuple[str, _CounterState]] = {}
        self._histograms: dict[str, tuple[str, _HistogramState]] = {}
        self._gauges: dict[str, tuple[str, _GaugeState]] = {}

    # ----- Counter -----

    def inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
        help_text: str = "",
    ) -> None:
        with self._lock:
            help_, state = self._counters.setdefault(name, (help_text, _CounterState()))
            state.inc(_normalize_labels(labels), value)
            if not help_ and help_text:
                self._counters[name] = (help_text, state)

    # ----- Histogram -----

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        buckets: Iterable[float] | None = None,
        help_text: str = "",
    ) -> None:
        with self._lock:
            existing = self._histograms.get(name)
            if existing is None:
                bucket_tuple = tuple(buckets) if buckets else DEFAULT_BUCKETS
                state = _HistogramState(buckets=bucket_tuple)
                self._histograms[name] = (help_text, state)
            else:
                _help, state = existing
            state.observe(_normalize_labels(labels), value)

    # ----- Gauge -----

    def gauge(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        with self._lock:
            help_, state = self._gauges.setdefault(name, (help_text, _GaugeState()))
            state.set(_normalize_labels(labels), value)
            if not help_ and help_text:
                self._gauges[name] = (help_text, state)

    # ----- Export -----

    def render_prometheus(self) -> str:
        """Возвращает текст в стандартном Prometheus exposition формате."""
        lines: list[str] = []
        with self._lock:
            for name, (help_text, state) in sorted(self._counters.items()):
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} counter")
                for labels, value in sorted(state.values.items()):
                    lines.append(f"{name}{_format_labels(labels)} {value}")

            for name, (help_text, gstate) in sorted(self._gauges.items()):
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} gauge")
                for labels, value in sorted(gstate.values.items()):
                    lines.append(f"{name}{_format_labels(labels)} {value}")

            for name, (help_text, hstate) in sorted(self._histograms.items()):
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} histogram")
                for labels, counts in sorted(hstate.bucket_counts.items()):
                    cumulative = 0
                    for i, upper in enumerate(hstate.buckets):
                        cumulative += counts[i]
                        bucket_labels = labels + (("le", str(upper)),)
                        lines.append(
                            f"{name}_bucket{_format_labels(bucket_labels)} {cumulative}"
                        )
                    inf_labels = labels + (("le", "+Inf"),)
                    cumulative += counts[-1]
                    lines.append(
                        f"{name}_bucket{_format_labels(inf_labels)} {cumulative}"
                    )
                    lines.append(
                        f"{name}_sum{_format_labels(labels)} "
                        f"{hstate.sums.get(labels, 0.0)}"
                    )
                    lines.append(
                        f"{name}_count{_format_labels(labels)} "
                        f"{hstate.counts.get(labels, 0)}"
                    )
        return "\n".join(lines) + ("\n" if lines else "")

    # ----- Helpers (для тестов) -----

    def counter_value(
        self, name: str, *, labels: dict[str, str] | None = None
    ) -> float:
        with self._lock:
            state = self._counters.get(name)
            if state is None:
                return 0.0
            return state[1].values.get(_normalize_labels(labels), 0.0)

    def histogram_count(
        self, name: str, *, labels: dict[str, str] | None = None
    ) -> int:
        with self._lock:
            entry = self._histograms.get(name)
            if entry is None:
                return 0
            return entry[1].counts.get(_normalize_labels(labels), 0)

    def histogram_sum(
        self, name: str, *, labels: dict[str, str] | None = None
    ) -> float:
        with self._lock:
            entry = self._histograms.get(name)
            if entry is None:
                return 0.0
            return entry[1].sums.get(_normalize_labels(labels), 0.0)

    def gauge_value(
        self, name: str, *, labels: dict[str, str] | None = None
    ) -> float | None:
        with self._lock:
            entry = self._gauges.get(name)
            if entry is None:
                return None
            return entry[1].values.get(_normalize_labels(labels))

    def reset(self) -> None:
        """Только для тестов."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()
