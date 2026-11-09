"""EmbeddingIndex (SETUP-12 / T-S12-013).

Утилиты для similarity-gate auto-allocator'а:
- EmbeddingComputer (Protocol) — обёртка над любым embedding-backend'ом.
- EmbeddingIndex — LRU-кэш для повторных запросов одного и того же текста.
- cosine_similarity utility.

Реальный backend (Ollama nomic-embed-text) подключается в S2.
"""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from typing import Protocol


class EmbeddingComputer(Protocol):
    """Контракт embedding-backend'а: текст → нормализованный вектор."""

    def compute(self, text: str) -> list[float]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity ∈ [-1, 1]. Нулевые векторы возвращают 0.0.

    Векторы могут быть разных размерностей только если оба пустые.
    """
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError(
            f"Vector dimensions mismatch: {len(a)} vs {len(b)}"
        )
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class EmbeddingIndex:
    """LRU-кэш embedding'ов поверх ``EmbeddingComputer``.

    Кэш-ключ — sha256 от input-текста. Capacity по умолчанию 1024
    записи (достаточно для покрытия среднего setup_job'а).
    """

    def __init__(
        self,
        computer: EmbeddingComputer,
        *,
        capacity: int = 1024,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._computer = computer
        self._capacity = capacity
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get_or_compute(self, text: str) -> list[float]:
        key = self._key(text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return list(self._cache[key])
            self._misses += 1
        vector = self._computer.compute(text)
        if not isinstance(vector, list):
            raise TypeError(
                f"EmbeddingComputer.compute must return list[float], "
                f"got {type(vector).__name__}"
            )
        with self._lock:
            self._cache[key] = list(vector)
            self._cache.move_to_end(key)
            while len(self._cache) > self._capacity:
                self._cache.popitem(last=False)
        return list(vector)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "capacity": self._capacity,
            }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @staticmethod
    def _key(text: str) -> str:
        import hashlib

        return hashlib.sha256(text.encode("utf-8")).hexdigest()
