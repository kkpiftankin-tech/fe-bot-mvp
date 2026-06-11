"""FastAPI app factory.

Точка входа для запуска `uvicorn fe_bot.app:create_app --factory --reload`.
"""

from __future__ import annotations

from fastapi import FastAPI

from fe_bot import __version__
from fe_bot.api.admin.router import router as admin_router
from fe_bot.api.dependencies import get_metrics
from fe_bot.api.observability.router import router as observability_router
from fe_bot.api.setup.router import router as setup_router
from fe_bot.api.setup.sources_router import router as sources_router
from fe_bot.api.setup.sse import router as setup_sse_router
from fe_bot.observability.middleware import RequestContextMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="FE-Bot API",
        description="Feature Engineering & Data Generation Multi-Agent Platform",
        version=__version__,
    )
    app.include_router(setup_router)
    app.include_router(sources_router)
    app.include_router(setup_sse_router)
    app.include_router(observability_router)
    app.include_router(admin_router)

    # Регистрируем metrics в app.state, чтобы middleware и тесты могли его
    # лениво читать (тесты переопределяют этот атрибут per-app).
    app.state.metrics = get_metrics()

    # Middleware последним добавляем (выполнится первым на запросе).
    app.add_middleware(RequestContextMiddleware)
    return app
