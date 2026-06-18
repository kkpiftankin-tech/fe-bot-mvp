"""SSE endpoint (T-S01-051).

GET /api/v1/setup/{setup_job_id}/events — Server-Sent Events stream.

Поведение:
1. Сначала отправляется история всех `SetupProgressEvent` для job (replay).
2. Дальше — подписка на live-события через EventBus.
3. Поток завершается, когда:
   - job достиг терминального статуса (ready / failed / cancelled);
   - клиент отключился (CancelledError);
   - превышен idle-timeout без новых событий.

Формат SSE (см. https://html.spec.whatwg.org/multipage/server-sent-events.html):

    event: setup.step.completed
    id: <event_index>
    data: {"setup_job_id": "...", "status": "...", ...}

    event: setup.kb.ready
    id: 5
    data: {...}
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import StreamingResponse
from schemas.setup.rag_setup_job import SetupJobStatus

from fe_bot.api.dependencies import (
    get_event_bus,
    get_orchestrator,
    require_permission,
)
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import Principal
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.repository import JobNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/setup", tags=["setup-sse"])

# Терминальные статусы — поток закрывается.
_TERMINAL = frozenset(
    {
        SetupJobStatus.READY,
        SetupJobStatus.FAILED,
        SetupJobStatus.CANCELLED,
    }
)
# Idle timeout по умолчанию: 60 секунд без новых событий → закрываем.
DEFAULT_IDLE_TIMEOUT_SECONDS = 60.0
# Heartbeat-комментарий каждые N секунд чтобы не отвалился proxy.
DEFAULT_HEARTBEAT_SECONDS = 15.0


def _format_sse(event: SetupProgressEvent, *, event_id: int) -> str:
    data_json = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"event: {event.event_type}\nid: {event_id}\ndata: {data_json}\n\n"


def _format_heartbeat() -> str:
    return ": heartbeat\n\n"


async def _event_stream(
    setup_job_id: str,
    event_bus: EventBus,
    orchestrator: SetupOrchestrator,
    *,
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
    heartbeat: float = DEFAULT_HEARTBEAT_SECONDS,
    max_events: int | None = None,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[SetupProgressEvent] = asyncio.Queue()

    def on_event(event: SetupProgressEvent) -> None:
        if event.setup_job_id != setup_job_id:
            return
        queue.put_nowait(event)

    event_bus.subscribe(on_event)
    event_index = 0
    try:
        # 1. Replay истории. Если в истории есть терминальное событие — закрываем.
        terminal_in_history = False
        for event in event_bus.history(setup_job_id):
            event_index += 1
            yield _format_sse(event, event_id=event_index)
            if _is_terminal(event):
                terminal_in_history = True
                break
            if max_events is not None and event_index >= max_events:
                return
        if terminal_in_history:
            return

        # После replay проверяем: вдруг job уже терминирован (но мы могли
        # пропустить событие, или job создан без событий)?
        try:
            job_state = orchestrator.get_job(setup_job_id)
            if job_state.status in _TERMINAL:
                return
        except JobNotFoundError:
            return

        # 2. Live-стриминг.
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            except TimeoutError:
                # Проверяем — может job уже терминирован?
                try:
                    job = orchestrator.get_job(setup_job_id)
                    if job.status in _TERMINAL:
                        return
                except JobNotFoundError:
                    return
                yield _format_heartbeat()
                # Если за idle_timeout не было событий — закрываем.
                if idle_timeout > 0 and heartbeat >= idle_timeout:
                    return
                continue

            event_index += 1
            yield _format_sse(event, event_id=event_index)
            if _is_terminal(event):
                return
            if max_events is not None and event_index >= max_events:
                return
    finally:
        event_bus.unsubscribe(on_event)


def _is_terminal(event: SetupProgressEvent) -> bool:
    if event.step in _TERMINAL:
        return True
    return event.status in ("ready", "failed", "cancelled")


@router.get(
    "/{setup_job_id}/events",
    summary="Stream setup progress events (T-S01-051)",
)
async def stream_events(
    setup_job_id: str = Path(..., min_length=1),
    principal: Principal = Depends(require_permission(Permission.KB_SETUP_CREATE)),
    orchestrator: SetupOrchestrator = Depends(get_orchestrator),
    event_bus: EventBus = Depends(get_event_bus),
) -> StreamingResponse:
    try:
        job = orchestrator.get_job(setup_job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # Только owner или privileged может слушать события.
    if job.user_id != principal.user_id and not principal.has_permission(Permission.KB_PUBLISH):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot subscribe to events of job owned by another user",
        )

    return StreamingResponse(
        _event_stream(setup_job_id, event_bus, orchestrator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # для nginx — отключает буферизацию
        },
    )
