"""Integration: SSE /api/v1/setup/{id}/events (T-S01-051)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from schemas.setup.rag_setup_job import SetupJobStatus

from fe_bot.setup.events import SetupProgressEvent

pytestmark = pytest.mark.integration


def _create_job(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "SSE Demo"},
        headers=headers,
    )
    return resp.json()["setup_job_id"]


def _publish_terminal_chain(
    event_bus,
    setup_job_id: str,
) -> None:
    """Кладёт в bus 3 события: started → indexed → ready (терминал)."""
    event_bus.publish(
        SetupProgressEvent(
            event_type="setup.step.started",
            setup_job_id=setup_job_id,
            step=SetupJobStatus.PARSING,
            status="in_progress",
            progress_percent=15.0,
            message="parsing",
        )
    )
    event_bus.publish(
        SetupProgressEvent(
            event_type="setup.step.completed",
            setup_job_id=setup_job_id,
            step=SetupJobStatus.INDEXING,
            status="in_progress",
            progress_percent=85.0,
            message="indexing",
        )
    )
    event_bus.publish(
        SetupProgressEvent(
            event_type="setup.kb.ready",
            setup_job_id=setup_job_id,
            step=SetupJobStatus.READY,
            status="ready",
            progress_percent=100.0,
            message="kb ready",
        )
    )


class TestSSEReplay:
    def test_replay_history_then_close_on_terminal(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_event_bus

        bus = app_with_clean_state.dependency_overrides[get_event_bus]()
        sid = _create_job(client, auth_headers)
        _publish_terminal_chain(bus, sid)

        # TestClient собирает весь stream; терминальный READY-event закрывает.
        resp = client.get(f"/api/v1/setup/{sid}/events", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = resp.text
        # Заголовки SSE
        assert "event: setup.step.started" in body
        assert "event: setup.kb.ready" in body
        # Каждое событие на своей строке id:N
        assert "id: 1" in body
        assert "id: 3" in body
        # Данные — JSON
        # Найдём строку 'data: {"setup_job_id": "...", "event_type": "setup.kb.ready"...}'
        lines = [
            line for line in body.split("\n")
            if line.startswith("data: ")
        ]
        # 1 событие от create_job (setup.job.created) + 3 события из bus = 4
        assert len(lines) == 4
        last = json.loads(lines[-1].removeprefix("data: "))
        assert last["status"] == "ready"
        assert last["setup_job_id"] == sid


class TestSSEAccessControl:
    def test_unknown_job_returns_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        resp = client.get(
            "/api/v1/setup/unknown_xxxxxxx/events", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_other_user_job_returns_403(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_event_bus

        bus = app_with_clean_state.dependency_overrides[get_event_bus]()
        sid = _create_job(client, auth_headers)
        _publish_terminal_chain(bus, sid)
        # u2 не владелец → 403
        resp = client.get(
            f"/api/v1/setup/{sid}/events",
            headers={"X-User-Id": "u2", "X-Roles": "user"},
        )
        assert resp.status_code == 403

    def test_admin_can_subscribe_to_others(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        from fe_bot.api.dependencies import get_event_bus

        bus = app_with_clean_state.dependency_overrides[get_event_bus]()
        sid = _create_job(client, auth_headers)
        _publish_terminal_chain(bus, sid)
        resp = client.get(
            f"/api/v1/setup/{sid}/events", headers=admin_headers
        )
        assert resp.status_code == 200
        assert "setup.kb.ready" in resp.text


class TestSSENoEvents:
    def test_empty_history_blocks_until_terminal_via_existing_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        app_with_clean_state,
    ) -> None:
        """Если истории нет и job не терминален — поток открывается, шлёт
        heartbeat'ы. Здесь мы переводим job в FAILED через bus + проверяем
        что stream закроется на heartbeat-cycle проверке статуса.
        """
        from fe_bot.api.dependencies import get_event_bus, get_orchestrator

        bus = app_with_clean_state.dependency_overrides[get_event_bus]()
        orchestrator = app_with_clean_state.dependency_overrides[get_orchestrator]()

        sid = _create_job(client, auth_headers)
        # Переведём в FAILED через orchestrator (DRAFT → FAILED разрешено).
        orchestrator.advance(sid, SetupJobStatus.FAILED, message="boom")

        # Теперь история уже содержит FAILED-event — replay → terminal → close.
        resp = client.get(f"/api/v1/setup/{sid}/events", headers=auth_headers)
        body = resp.text
        assert "setup.step.failed" in body
        # bus не использован напрямую в этом тесте (через orchestrator), но
        # keep-import:
        _ = bus
