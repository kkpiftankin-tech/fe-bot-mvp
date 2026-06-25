"""Observability router (T-S01-049 / T-S01-050 + OBS-LLM-01).

GET /metrics       — Prometheus exposition.
GET /healthz       — liveness probe.
GET /readyz        — readiness probe.
GET /api/v1/observability/llm-stats — runtime LLM call stats для UI progress bar.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from fe_bot.api.dependencies import get_llm_stats, get_metrics
from fe_bot.observability.llm_stats import LLMStatsCollector
from fe_bot.observability.metrics import MetricsRegistry

router = APIRouter(tags=["observability"])


@router.get("/metrics", response_class=Response, include_in_schema=False)
def get_metrics_endpoint(
    metrics: MetricsRegistry = Depends(get_metrics),
) -> Response:
    text = metrics.render_prometheus()
    return Response(
        content=text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
def readyz() -> dict[str, str]:
    # В MVP считаем сервис готовым если процесс отвечает.
    # В INF-005 здесь будут проверки PostgreSQL/Redis/Qdrant.
    return {"status": "ready"}


# ============================================================
# OBS-LLM-01: LLM call stats для UI progress bar
# ============================================================


class _ModelStatsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    model: str = Field(..., alias="model")
    count: int
    avg_ms: float
    p50_ms: float
    p95_ms: float
    last_ms: int | None = None


class _LLMStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[_ModelStatsDTO]
    total_calls: int


@router.get(
    "/api/v1/observability/llm-stats",
    response_model=_LLMStatsResponse,
    summary="Runtime LLM call latency stats (OBS-LLM-01)",
)
def get_llm_call_stats(
    stats: LLMStatsCollector = Depends(get_llm_stats),
) -> _LLMStatsResponse:
    """Возвращает avg/p50/p95 latency и счётчик вызовов per модель.

    Используется фронтом для отображения progress bar каждого LLM-вызова:
    клиент берёт avg/p95 для модели и линейно анимирует до этого значения,
    после чего переключается в indeterminate-режим.
    """
    items = stats.snapshot()
    return _LLMStatsResponse(
        models=[
            _ModelStatsDTO(
                model=s.model,
                count=s.count,
                avg_ms=s.avg_ms,
                p50_ms=s.p50_ms,
                p95_ms=s.p95_ms,
                last_ms=s.last_ms,
            )
            for s in items
        ],
        total_calls=sum(s.count for s in items),
    )
