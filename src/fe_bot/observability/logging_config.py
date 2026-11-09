"""Structured Logging (T-S01-050).

JSON-formatter + correlation_id через contextvars.

Использование:
1. На старте приложения вызвать `configure_json_logging()`.
2. HTTP-middleware (см. middleware.py) ставит `correlation_id` через
   `set_correlation_id()` на каждом запросе.
3. Любой код может вызвать `with_request_context()` для прикрепления
   дополнительных полей (setup_job_id, user_id).

JSON shape:
{
  "timestamp": "2026-06-10T10:00:00.000Z",
  "level": "INFO",
  "logger": "fe_bot.setup.pipeline",
  "message": "Pipeline started",
  "correlation_id": "req_xyz",
  "setup_job_id": "setup_abc",   // если установлен
  "user_id": "u1",                // если установлен
  ...extra fields
}
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variables — propagate через await chain.
_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
# default=None для мутабельного типа; пустой dict материализуем при чтении.
_request_context_ctx: ContextVar[dict[str, Any] | None] = ContextVar(
    "request_context", default=None
)


def set_correlation_id(correlation_id: str | None) -> None:
    """Привязывает correlation_id к текущему async-контексту."""
    _correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()


def with_request_context(**kwargs: Any) -> None:
    """Добавляет произвольные поля в request context (setup_job_id, user_id, etc)."""
    current = dict(_request_context_ctx.get() or {})
    current.update(kwargs)
    _request_context_ctx.set(current)


def clear_request_context() -> None:
    """Очищает request context (в конце запроса)."""
    _request_context_ctx.set(None)


# Стандартные поля LogRecord, которые не нужно дублировать в `extra`.
_STD_RECORD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
    }
)


class JSONFormatter(logging.Formatter):
    """Logging formatter, выдающий по одной JSON-записи на строку."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Прикрепляем correlation_id если есть.
        correlation_id = _correlation_id_ctx.get()
        if correlation_id:
            payload["correlation_id"] = correlation_id

        # Поля request context.
        context = _request_context_ctx.get() or {}
        if context:
            payload.update(context)

        # Любые `extra=` поля, переданные через `logger.info(..., extra={"foo": "bar"})`.
        for key, value in record.__dict__.items():
            if key in _STD_RECORD_FIELDS:
                continue
            if key.startswith("_"):
                continue
            if key in payload:
                # не перетираем стандартные ключи
                continue
            payload[key] = _safe_value(value)

        # Exception info.
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def _safe_value(value: Any) -> Any:
    """Делает значение JSON-serializable (fallback на str)."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Настраивает root-logger на JSON output в stdout."""
    root = logging.getLogger()
    # Удаляем существующие handlers (в т.ч. uvicorn default).
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(level)
