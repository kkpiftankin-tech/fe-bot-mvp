"""Observability router (T-S01-049 / T-S01-050).

GET /metrics — Prometheus exposition.
GET /healthz — liveness probe (нет зависимостей).
GET /readyz  — readiness probe (проверка зависимостей; в MVP заглушка).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from fe_bot.api.dependencies import get_metrics
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
