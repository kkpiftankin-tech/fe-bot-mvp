"""FastAPI app factory.

Точка входа для запуска `uvicorn fe_bot.app:create_app --factory --reload`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from fe_bot import __version__
from fe_bot.api.admin.router import router as admin_router
from fe_bot.api.dependencies import get_metrics
from fe_bot.api.observability.router import router as observability_router
from fe_bot.api.setup.parse_router import router as parse_router
from fe_bot.api.setup.rag_cards_router import router as rag_cards_router
from fe_bot.api.setup.chunking_router import router as chunking_router
from fe_bot.api.setup.review_router import router as review_router
from fe_bot.api.setup.router import router as setup_router
from fe_bot.api.setup.validation_router import router as validation_router
from fe_bot.api.setup.sources_router import router as sources_router
from fe_bot.api.setup.sse import router as setup_sse_router
from fe_bot.observability.middleware import RequestContextMiddleware
from fe_bot.persistence import SnapshotPersister, register_default_state

logger = logging.getLogger(__name__)


def _persistence_disabled() -> bool:
    return os.environ.get("FE_BOT_DISABLE_PERSISTENCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    persister: SnapshotPersister | None = None
    if not _persistence_disabled():
        persister = SnapshotPersister()
        register_default_state(persister)
        try:
            persister.load()
        except Exception:  # noqa: BLE001
            logger.exception("Snapshot load failed; continuing with empty state")
    app.state.snapshot_persister = persister
    try:
        yield
    finally:
        if persister is not None:
            try:
                persister.save()
            except Exception:  # noqa: BLE001
                logger.exception("Snapshot save failed at shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="FE-Bot API",
        description="Feature Engineering & Data Generation Multi-Agent Platform",
        version=__version__,
        lifespan=_lifespan,
    )
    app.include_router(setup_router)
    app.include_router(sources_router)
    app.include_router(parse_router)
    app.include_router(rag_cards_router)
    app.include_router(review_router)
    app.include_router(validation_router)
    app.include_router(chunking_router)
    app.include_router(setup_sse_router)
    app.include_router(observability_router)
    app.include_router(admin_router)

    # Регистрируем metrics в app.state, чтобы middleware и тесты могли его
    # лениво читать (тесты переопределяют этот атрибут per-app).
    app.state.metrics = get_metrics()

    # После каждого мутирующего запроса делаем snapshot — это переживёт
    # внезапный SIGKILL (а не только graceful shutdown). Запись дешёвая
    # (~50ms на пустом state, до 1с при тысячах документов).
    @app.middleware("http")
    async def _autosave_state(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and 200 <= response.status_code < 400
        ):
            persister = getattr(request.app.state, "snapshot_persister", None)
            if persister is not None:
                try:
                    persister.save()
                except Exception:  # noqa: BLE001
                    logger.exception("Autosave snapshot failed")
        return response

    # Middleware последним добавляем (выполнится первым на запросе).
    app.add_middleware(RequestContextMiddleware)
    return app
