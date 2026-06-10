"""SetupProgressEvent (DTO-49 underlying schema) + in-process EventBus.

В S1 события публикуются в локальную очередь (для тестов и SSE).
В S8 заменяется на Kafka producer.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from schemas.setup.rag_setup_job import SetupJobStatus


class SetupProgressEvent(BaseModel):
    """Событие прогресса setup-pipeline.

    Структура из SETUP-01 §15.2.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    step: SetupJobStatus | None = None
    status: str = Field(..., min_length=1)
    progress_percent: float = Field(..., ge=0.0, le=100.0)
    message: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


EventHandler = Callable[[SetupProgressEvent], None]


class EventBus:
    """Простой in-process pub/sub. В S8 замены — Kafka producer/consumer."""

    def __init__(self) -> None:
        self._subscribers: list[EventHandler] = []
        self._history: list[SetupProgressEvent] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._subscribers.append(handler)

    def unsubscribe(self, handler: EventHandler) -> None:
        """Идемпотентно: noop если handler уже не подписан."""
        with contextlib.suppress(ValueError):
            self._subscribers.remove(handler)

    def publish(self, event: SetupProgressEvent) -> None:
        self._history.append(event)
        # Делаем снимок чтобы handlers могли отписываться внутри callback.
        for handler in list(self._subscribers):
            handler(event)

    def history(self, setup_job_id: str | None = None) -> list[SetupProgressEvent]:
        if setup_job_id is None:
            return list(self._history)
        return [e for e in self._history if e.setup_job_id == setup_job_id]

    def clear(self) -> None:
        """Для тестов."""
        self._subscribers.clear()
        self._history.clear()
