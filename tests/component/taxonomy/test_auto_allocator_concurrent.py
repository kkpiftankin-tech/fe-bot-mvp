"""Concurrency-тесты AutoAllocator (SETUP-12 / T-S12-021).

Покрывает: при параллельных NEW-предложениях похожих классов под
одним parent_path advisory-lock + slug/similarity-gate гарантируют,
что класс материализуется ровно один раз.

См. ADR-HTC-04 — invariant: «Параллельные классификации не создают
дубликаты: вторая после lock'а увидит уже добавленный класс».
"""

from __future__ import annotations

import threading
from collections import Counter
from datetime import UTC, datetime

import pytest
from schemas.taxonomy.decision import NewClassProposal
from schemas.taxonomy.registry import TaxonomyVersion

from fe_bot.taxonomy import (
    AllocationSource,
    AutoAllocator,
    AutoAllocatorConfig,
    EmbeddingIndex,
    TaxonomyRegistry,
)
from fe_bot.taxonomy.auto_allocator import AllocationResult

pytestmark = pytest.mark.component


class _DeterministicComputer:
    """Embedding-stub с табличным вычислением + лёгкой задержкой,
    чтобы прокрашивать race-condition'ы."""

    def __init__(
        self,
        table: dict[str, list[float]] | None = None,
        *,
        delay_sec: float = 0.0,
    ) -> None:
        self._table = table or {}
        self._delay_sec = delay_sec
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def compute(self, text: str) -> list[float]:
        if self._delay_sec > 0:
            import time

            time.sleep(self._delay_sec)
        with self._lock:
            self.calls.append(text)
        return list(self._table.get(text, [0.5, 0.5, 0.5]))


def _make_registry() -> TaxonomyRegistry:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(
        TaxonomyVersion(
            version_id="v1.0.0",
            created_at=datetime.now(tz=UTC),
            is_active=True,
            entries=[],
        )
    )
    return reg


class TestConcurrentSameSlug:
    def test_5_parallel_with_identical_slug_produce_one_class(self) -> None:
        """5 потоков предлагают РОВНО ТОТ ЖЕ name_slug — должен быть
        ровно один auto_create, остальные slug_match."""
        reg = _make_registry()
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(_DeterministicComputer(delay_sec=0.005)),
            config=AutoAllocatorConfig(),
        )
        proposal = NewClassProposal(
            name_slug="shared-class",
            display_name_ru="Общий класс",
            display_name_en="",
            description="Описание общего класса для теста concurrency.",
        )
        results: list[AllocationResult] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(5)

        def worker() -> None:
            barrier.wait()
            r = allocator.allocate(
                proposal,
                level=1,
                parent_path="task",
                triggered_by_section_id=f"sec_{threading.get_ident()}",
            )
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        sources = Counter(r.source for r in results)
        # Ровно один auto_create
        assert sources[AllocationSource.AUTO_CREATE] == 1
        # Остальные — slug_match (advisory-lock сериализовал)
        assert sources[AllocationSource.SLUG_MATCH] == 4
        # И все ссылаются на один bit_index
        bits = {r.bit_index for r in results}
        assert len(bits) == 1

        # Final state: один класс в registry под task L1
        l1 = reg.list_active_under(level=1, parent_path="task")
        assert len(l1) == 1
        assert l1[0].class_slug == "shared-class"

    def test_5_parallel_with_similar_embeddings_produce_one_class(self) -> None:
        """5 потоков с РАЗНЫМИ slug, но идентичными embedding'ами —
        первый auto_create, остальные similarity_reuse."""
        reg = _make_registry()
        # Все proposals → один и тот же embedding vector (точная копия)
        same_vec = [1.0, 0.0, 0.0]
        table = {}
        for i in range(5):
            text = f"Класс-{i} Описание тестового класса {i}."
            table[text] = list(same_vec)
        stub = _DeterministicComputer(table, delay_sec=0.005)
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(stub),
            config=AutoAllocatorConfig(),
        )
        results: list[AllocationResult] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(5)

        def worker(i: int) -> None:
            proposal = NewClassProposal(
                name_slug=f"class-{i}",
                display_name_ru=f"Класс-{i}",
                display_name_en="",
                description=f"Описание тестового класса {i}.",
            )
            barrier.wait()
            r = allocator.allocate(
                proposal,
                level=1,
                parent_path="task",
                triggered_by_section_id=f"sec_{i}",
            )
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        sources = Counter(r.source for r in results)
        # Ровно один auto_create
        assert sources[AllocationSource.AUTO_CREATE] == 1
        # Остальные — similarity_reuse (embedding'и идентичны)
        assert sources[AllocationSource.SIMILARITY_REUSE] == 4

        # Final state: один класс в registry
        l1 = reg.list_active_under(level=1, parent_path="task")
        assert len(l1) == 1

    def test_independent_parent_paths_allocate_independently(self) -> None:
        """Разные parent_path'ы не блокируют друг друга — у каждого
        свой lock."""
        reg = _make_registry()
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(_DeterministicComputer()),
            config=AutoAllocatorConfig(),
        )
        results: list[AllocationResult] = []
        results_lock = threading.Lock()

        def worker(parent: str, slug: str) -> None:
            proposal = NewClassProposal(
                name_slug=slug,
                display_name_ru=f"Класс {slug}",
                display_name_en="",
                description=f"Описание класса {slug} для теста.",
            )
            r = allocator.allocate(
                proposal,
                level=1,
                parent_path=parent,
                triggered_by_section_id=f"sec_{parent}_{slug}",
            )
            with results_lock:
                results.append(r)

        threads = [
            threading.Thread(target=worker, args=("task", "pvo")),
            threading.Thread(target=worker, args=("schema", "etl")),
            threading.Thread(target=worker, args=("analytics", "anomaly")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Все три — auto_create под своими parent_path
        assert all(r.source == AllocationSource.AUTO_CREATE for r in results)
        assert len(reg.list_active_under(level=1, parent_path="task")) == 1
        assert len(reg.list_active_under(level=1, parent_path="schema")) == 1
        assert (
            len(reg.list_active_under(level=1, parent_path="analytics")) == 1
        )
