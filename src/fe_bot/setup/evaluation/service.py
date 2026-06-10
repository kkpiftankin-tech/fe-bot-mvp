"""RAG Evaluation Service (T-S01-036).

Прогоняет golden set из (query, expected_doc_ids) через RetrievalService и
считает метрики (см. docs/06-rag/quality-gates.md):

- `recall@k`     = |relevant ∩ retrieved_top_k| / |relevant|
- `precision@k`  = |relevant ∩ retrieved_top_k| / |retrieved_top_k|
- `mrr`          = mean reciprocal rank первого relevant
- `no_context_rate` = доля запросов с пустым результатом

Gate-проверка: pass если `mean(recall@5) >= MIN_RETRIEVAL_RECALL_AT_5`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from schemas.common.defaults import MIN_RETRIEVAL_RECALL_AT_5

from fe_bot.retrieval.service import RetrievalRequest, RetrievalService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GoldenQuery:
    """Один пункт golden dataset для retrieval-eval."""

    query: str
    expected_doc_ids: list[str]
    doc_types: list[str] | None = None
    description: str | None = None


@dataclass(slots=True)
class PerQueryEval:
    """Результат eval по одному запросу."""

    query: str
    expected_doc_ids: list[str]
    retrieved_doc_ids: list[str]
    recall_at_k: float
    precision_at_k: float
    reciprocal_rank: float
    is_no_context: bool
    error_message: str | None = None


@dataclass(slots=True)
class EvalReport:
    """Сводка eval по всему golden set."""

    queries_total: int = 0
    queries_errored: int = 0
    top_k: int = 5
    threshold_recall_at_5: float = MIN_RETRIEVAL_RECALL_AT_5
    mean_recall_at_k: float = 0.0
    mean_precision_at_k: float = 0.0
    mean_reciprocal_rank: float = 0.0
    no_context_rate: float = 0.0
    per_query: list[PerQueryEval] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Gate: mean recall@5 ≥ threshold AND нет errors."""
        if self.queries_errored > 0:
            return False
        return self.mean_recall_at_k >= self.threshold_recall_at_5


class RAGEvaluationService:
    """Прогон golden set через retrieval + расчёт метрик."""

    def __init__(
        self,
        *,
        retrieval: RetrievalService,
        threshold_recall_at_5: float = MIN_RETRIEVAL_RECALL_AT_5,
    ) -> None:
        self._retrieval = retrieval
        self._threshold = threshold_recall_at_5

    def evaluate(
        self,
        golden_queries: Iterable[GoldenQuery],
        *,
        top_k: int = 5,
    ) -> EvalReport:
        queries = list(golden_queries)
        if not queries:
            return EvalReport(
                queries_total=0,
                top_k=top_k,
                threshold_recall_at_5=self._threshold,
            )

        report = EvalReport(
            queries_total=len(queries),
            top_k=top_k,
            threshold_recall_at_5=self._threshold,
        )
        recalls: list[float] = []
        precisions: list[float] = []
        rrs: list[float] = []
        no_context_count = 0

        for gq in queries:
            request = RetrievalRequest(
                query=gq.query,
                top_k=top_k,
                doc_types=gq.doc_types,
                deduplicate_by_doc=True,
            )
            retrieval_result = self._retrieval.search(request)
            per_query = self._build_per_query(
                gq=gq, retrieved_doc_ids=retrieval_result.doc_ids,
                error_message=retrieval_result.error_message,
            )
            report.per_query.append(per_query)
            if per_query.error_message:
                report.queries_errored += 1
                continue
            recalls.append(per_query.recall_at_k)
            precisions.append(per_query.precision_at_k)
            rrs.append(per_query.reciprocal_rank)
            if per_query.is_no_context:
                no_context_count += 1

        evaluated = report.queries_total - report.queries_errored
        if evaluated > 0:
            report.mean_recall_at_k = sum(recalls) / evaluated
            report.mean_precision_at_k = sum(precisions) / evaluated
            report.mean_reciprocal_rank = sum(rrs) / evaluated
            report.no_context_rate = no_context_count / evaluated
        return report

    @staticmethod
    def _build_per_query(
        *,
        gq: GoldenQuery,
        retrieved_doc_ids: list[str],
        error_message: str | None,
    ) -> PerQueryEval:
        if error_message:
            return PerQueryEval(
                query=gq.query,
                expected_doc_ids=list(gq.expected_doc_ids),
                retrieved_doc_ids=retrieved_doc_ids,
                recall_at_k=0.0,
                precision_at_k=0.0,
                reciprocal_rank=0.0,
                is_no_context=True,
                error_message=error_message,
            )

        expected = set(gq.expected_doc_ids)
        retrieved_set = set(retrieved_doc_ids)
        relevant_retrieved = expected & retrieved_set

        recall = (
            len(relevant_retrieved) / len(expected) if expected else 0.0
        )
        precision = (
            len(relevant_retrieved) / len(retrieved_doc_ids)
            if retrieved_doc_ids
            else 0.0
        )
        # Reciprocal rank: 1/rank первого expected doc (1-indexed); 0 если не найден.
        rr = 0.0
        for idx, doc_id in enumerate(retrieved_doc_ids, start=1):
            if doc_id in expected:
                rr = 1.0 / idx
                break
        return PerQueryEval(
            query=gq.query,
            expected_doc_ids=list(gq.expected_doc_ids),
            retrieved_doc_ids=retrieved_doc_ids,
            recall_at_k=recall,
            precision_at_k=precision,
            reciprocal_rank=rr,
            is_no_context=not retrieved_doc_ids,
        )
