"""HTTP Middleware (T-S01-050).

RequestContextMiddleware:
- Извлекает `X-Request-Id` или генерирует новый.
- Ставит correlation_id в contextvar (для structured logging).
- Прикрепляет user_id из X-User-Id (если есть).
- Замеряет latency и инкрементит метрики:
    - `http_requests_total{method, status_class}`
    - `http_request_duration_seconds{method}` histogram

Metrics-registry читается лениво из `app.state.metrics` (или из переданного
callable), чтобы тесты могли переопределять registry per-app.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from fe_bot.observability.logging_config import (
    clear_request_context,
    set_correlation_id,
    with_request_context,
)
from fe_bot.observability.metrics import MetricsRegistry


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Прикрепляет correlation_id + замеряет HTTP-метрики."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"
        set_correlation_id(request_id)

        user_id = request.headers.get("X-User-Id")
        ctx: dict[str, str] = {"http_method": request.method, "http_path": request.url.path}
        if user_id:
            ctx["user_id"] = user_id
        with_request_context(**ctx)

        metrics = _get_metrics(request)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.perf_counter() - start
            _record_metrics(metrics, request.method, "5xx", elapsed)
            clear_request_context()
            set_correlation_id(None)
            raise

        elapsed = time.perf_counter() - start
        response.headers["X-Request-Id"] = request_id

        status_class = f"{response.status_code // 100}xx"
        _record_metrics(metrics, request.method, status_class, elapsed)

        clear_request_context()
        set_correlation_id(None)
        return response


def _get_metrics(request: Request) -> MetricsRegistry | None:
    """Возвращает registry из app.state или None если не задан."""
    return getattr(request.app.state, "metrics", None)


def _record_metrics(
    metrics: MetricsRegistry | None,
    method: str,
    status_class: str,
    elapsed_seconds: float,
) -> None:
    if metrics is None:
        return
    metrics.inc(
        "http_requests_total",
        labels={"method": method, "status_class": status_class},
        help_text="HTTP requests count by method and status class",
    )
    metrics.observe(
        "http_request_duration_seconds",
        elapsed_seconds,
        labels={"method": method},
        help_text="HTTP request duration in seconds",
    )
