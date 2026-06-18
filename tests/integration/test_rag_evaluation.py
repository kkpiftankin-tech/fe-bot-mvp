"""Integration: RAG Evaluation Service (T-S01-036)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from fe_bot.retrieval.service import RetrievalRequest, RetrievalResult
from fe_bot.setup.evaluation.service import (
    GoldenQuery,
    RAGEvaluationService,
)
from fe_bot.vector_index.client import SearchHit

pytestmark = pytest.mark.integration


@dataclass
class StubRetrievalService:
    """Fake RetrievalService — даёт результат из заранее заданной таблицы."""

    responses: dict[str, list[str]]
    error_on: set[str] | None = None

    def search(self, request: RetrievalRequest) -> RetrievalResult:
        if self.error_on and request.query in self.error_on:
            return RetrievalResult(
                query=request.query,
                top_k=request.top_k,
                hits=[],
                error_message="LLM unavailable for query embedding",
            )
        doc_ids = self.responses.get(request.query, [])
        hits = [
            SearchHit(
                chunk_id=f"{doc_id}#summary#0",
                doc_id=doc_id,
                score=1.0 - 0.1 * i,
                payload={"doc_id": doc_id},
            )
            for i, doc_id in enumerate(doc_ids[: request.top_k])
        ]
        return RetrievalResult(
            query=request.query,
            top_k=request.top_k,
            hits=hits,
            collections_searched=["rag_analytics_card"],
        )


class TestRecallAtK:
    def test_perfect_recall(self) -> None:
        retrieval = StubRetrievalService(responses={"q1": ["a", "b", "c"]})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate([GoldenQuery(query="q1", expected_doc_ids=["a", "b", "c"])], top_k=3)
        assert report.queries_total == 1
        assert report.mean_recall_at_k == 1.0
        assert report.mean_precision_at_k == 1.0
        assert report.mean_reciprocal_rank == 1.0
        assert report.no_context_rate == 0.0

    def test_partial_recall(self) -> None:
        # Только 1 из 2 expected найдены.
        retrieval = StubRetrievalService(responses={"q1": ["a", "x", "y", "z", "w"]})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate([GoldenQuery(query="q1", expected_doc_ids=["a", "b"])], top_k=5)
        # recall = 1/2 = 0.5; precision = 1/5 = 0.2; rr = 1/1 = 1.0.
        assert report.mean_recall_at_k == 0.5
        assert report.mean_precision_at_k == 0.2
        assert report.mean_reciprocal_rank == 1.0

    def test_zero_recall(self) -> None:
        retrieval = StubRetrievalService(responses={"q1": ["x", "y", "z"]})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate([GoldenQuery(query="q1", expected_doc_ids=["a", "b"])], top_k=3)
        assert report.mean_recall_at_k == 0.0
        assert report.mean_precision_at_k == 0.0
        assert report.mean_reciprocal_rank == 0.0
        assert report.no_context_rate == 0.0  # есть hits, просто не expected


class TestNoContext:
    def test_no_context_rate(self) -> None:
        # q1 → есть hits, q2 → пусто.
        retrieval = StubRetrievalService(responses={"q1": ["a"], "q2": []})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate(
            [
                GoldenQuery(query="q1", expected_doc_ids=["a"]),
                GoldenQuery(query="q2", expected_doc_ids=["b"]),
            ],
            top_k=5,
        )
        assert report.no_context_rate == 0.5


class TestReciprocalRank:
    def test_rr_first_position(self) -> None:
        retrieval = StubRetrievalService(responses={"q": ["a", "b", "c"]})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate([GoldenQuery(query="q", expected_doc_ids=["a"])], top_k=3)
        assert report.mean_reciprocal_rank == 1.0

    def test_rr_third_position(self) -> None:
        retrieval = StubRetrievalService(responses={"q": ["x", "y", "a"]})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate([GoldenQuery(query="q", expected_doc_ids=["a"])], top_k=3)
        assert abs(report.mean_reciprocal_rank - 1 / 3) < 1e-9


class TestGate:
    def test_passes_above_threshold(self) -> None:
        # Threshold default = 0.85.
        retrieval = StubRetrievalService(
            responses={
                # 1.0 recall если expected — подмножество retrieved.
                "q1": ["a", "b", "c", "d", "e"],
                "q2": ["a", "b", "c", "d", "e"],
            }
        )
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate(
            [
                GoldenQuery(query="q1", expected_doc_ids=["a"]),
                GoldenQuery(query="q2", expected_doc_ids=["b"]),
            ],
            top_k=5,
        )
        assert report.passed is True

    def test_fails_below_threshold(self) -> None:
        retrieval = StubRetrievalService(responses={"q1": [], "q2": []})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate(
            [
                GoldenQuery(query="q1", expected_doc_ids=["a"]),
                GoldenQuery(query="q2", expected_doc_ids=["b"]),
            ],
            top_k=5,
        )
        assert report.passed is False
        assert report.mean_recall_at_k == 0.0

    def test_errors_fail_gate(self) -> None:
        # Даже если успешные queries проходят, errored запросы фейлят gate.
        retrieval = StubRetrievalService(
            responses={"q1": ["a"], "q2": ["b"]},
            error_on={"q2"},
        )
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate(
            [
                GoldenQuery(query="q1", expected_doc_ids=["a"]),
                GoldenQuery(query="q2", expected_doc_ids=["b"]),
            ],
            top_k=5,
        )
        assert report.queries_errored == 1
        assert report.passed is False

    def test_custom_threshold(self) -> None:
        retrieval = StubRetrievalService(responses={"q": ["a"]})
        svc = RAGEvaluationService(
            retrieval=retrieval,  # type: ignore[arg-type]
            threshold_recall_at_5=0.4,
        )
        report = svc.evaluate([GoldenQuery(query="q", expected_doc_ids=["a", "b"])], top_k=5)
        # recall = 0.5 > 0.4 → passed
        assert report.passed is True


class TestEmptyInput:
    def test_empty_golden_set(self) -> None:
        retrieval = StubRetrievalService(responses={})
        svc = RAGEvaluationService(retrieval=retrieval)  # type: ignore[arg-type]
        report = svc.evaluate([], top_k=5)
        assert report.queries_total == 0
        assert report.mean_recall_at_k == 0.0
        # Пустой golden set не должен «проходить» gate (нет данных).
        # passed = mean(recall) >= threshold; 0 >= 0.85 = False.
        assert report.passed is False
