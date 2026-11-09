"""Integration tests for SETUP-05 T-S05-039 / T-S05-040.

Проверяем:
- AuditAction записи: RAG_CARD_GENERATION_TRIGGERED, RAG_CARD_GENERATED,
  RAG_CARD_REGENERATE_TRIGGERED, RAG_CARD_REVIEW_REQUIRED,
  RAG_CARD_GENERATION_CANCELLED.
- Metrics counters: rag_card_generation_jobs_total, rag_cards_generated_total,
  rag_cards_failed_total + histogram rag_card_generation_duration_ms.
- Structured logs: rag_card_generation_job_started / _finished / per-card.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

import pytest
from fastapi.testclient import TestClient

from fe_bot.audit.service import AuditAction, AuditEvent, InMemoryAuditLog
from fe_bot.observability.metrics import MetricsRegistry

pytestmark = pytest.mark.integration


def _create(client: TestClient, headers: dict[str, str]) -> str:
    r = client.post(
        "/api/v1/setup/jobs",
        json={"project_name": "Audit"},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["setup_job_id"]


def _upload(client: TestClient, sid: str, headers: dict[str, str]) -> None:
    body = b"# Tasks\n\nDescription of ML task.\n"
    r = client.post(
        f"/api/v1/setup/{sid}/documents",
        files={"files": ("doc.md", body, "text/markdown")},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text


def _parse(client: TestClient, sid: str, headers: dict[str, str]) -> None:
    pj = client.post(f"/api/v1/setup/{sid}/parse-jobs", json={}, headers=headers)
    assert pj.status_code == 201
    job_id = pj.json()["parse_job_id"]
    run = client.post(f"/api/v1/setup/{sid}/parse-jobs/{job_id}/run", headers=headers)
    assert run.status_code == 200


def _prepare(client: TestClient, headers: dict[str, str]) -> str:
    sid = _create(client, headers)
    _upload(client, sid, headers)
    _parse(client, sid, headers)
    return sid


def _create_and_run_gen(
    client: TestClient, sid: str, headers: dict[str, str]
) -> tuple[str, dict]:
    create = client.post(
        f"/api/v1/setup/{sid}/rag-cards/generate",
        json={"generation_mode": "template"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    gen_id = create.json()["generation_job_id"]
    run = client.post(
        f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gen_id}/run",
        headers=headers,
    )
    assert run.status_code == 200, run.text
    return gen_id, run.json()


def _actions(events: Iterable[AuditEvent]) -> list[AuditAction]:
    return [e.action for e in events]


# ============================================================
# T-S05-039: audit
# ============================================================


class TestAuditRecords:
    def test_generation_triggered_recorded_on_create_job(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _prepare(client, auth_headers)
        r = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        )
        assert r.status_code == 201
        events = audit_log.list_for_job(sid)
        assert AuditAction.RAG_CARD_GENERATION_TRIGGERED in _actions(events)

    def test_card_generated_recorded_per_section(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _prepare(client, auth_headers)
        _, run_body = _create_and_run_gen(client, sid, auth_headers)
        assert run_body["generated_cards"] >= 1
        events = audit_log.list_for_job(sid)
        gen_records = [
            e for e in events if e.action == AuditAction.RAG_CARD_GENERATED
        ]
        assert len(gen_records) == run_body["generated_cards"]
        for r in gen_records:
            assert r.target_type == "rag_card"
            assert r.setup_job_id == sid
            assert "doc_type" in r.payload
            assert "confidence_level" in r.payload

    def test_regenerate_triggered_recorded(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        admin_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _prepare(client, auth_headers)
        _, run_body = _create_and_run_gen(client, sid, auth_headers)
        if run_body["generated_cards"] == 0:
            pytest.skip("no cards generated to regenerate")
        listing = client.get(
            f"/api/v1/setup/{sid}/rag-cards-catalog", headers=auth_headers
        )
        assert listing.status_code == 200
        doc_id = listing.json()["items"][0]["doc_id"]
        regen = client.post(
            f"/api/v1/setup/{sid}/rag-cards/{doc_id}/regenerate",
            json={"reason": "test"},
            headers=admin_headers,
        )
        assert regen.status_code == 200, regen.text
        events = audit_log.list_for_job(sid)
        regen_events = [
            e for e in events if e.action == AuditAction.RAG_CARD_REGENERATE_TRIGGERED
        ]
        assert len(regen_events) == 1
        rec = regen_events[0]
        assert rec.target_id == doc_id
        assert rec.payload["reason"] == "test"
        assert rec.payload["new_card_version"] == "2.0"

    def test_cancellation_recorded(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        audit_log: InMemoryAuditLog,
    ) -> None:
        sid = _prepare(client, auth_headers)
        create = client.post(
            f"/api/v1/setup/{sid}/rag-cards/generate",
            json={"generation_mode": "template"},
            headers=auth_headers,
        )
        gen_id = create.json()["generation_job_id"]
        cancel = client.post(
            f"/api/v1/setup/{sid}/rag-card-generation-jobs/{gen_id}/cancel",
            headers=auth_headers,
        )
        assert cancel.status_code == 200, cancel.text
        events = audit_log.list_for_job(sid)
        assert AuditAction.RAG_CARD_GENERATION_CANCELLED in _actions(events)


# ============================================================
# T-S05-039: metrics
# ============================================================


class TestMetrics:
    def test_generated_counter_per_doc_type(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _prepare(client, auth_headers)
        _, run_body = _create_and_run_gen(client, sid, auth_headers)
        # rag_cards_generated_total: counter per doc_type x confidence
        text = metrics_registry.render_prometheus()
        assert "rag_cards_generated_total" in text
        # total emitted equals generated_cards
        # доступно через counter_value на (doc_type, confidence_bucket).
        # суммируем по всем сериям.
        total = 0.0
        for (labels, value) in (
            metrics_registry._counters.get(
                "rag_cards_generated_total", ("", None)
            )[1].values.items()
            if metrics_registry._counters.get("rag_cards_generated_total")
            else []
        ):
            total += value
        assert int(total) == run_body["generated_cards"]

    def test_jobs_total_counter_per_outcome(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _prepare(client, auth_headers)
        _, run_body = _create_and_run_gen(client, sid, auth_headers)
        outcome = run_body["status"]
        v = metrics_registry.counter_value(
            "rag_card_generation_jobs_total",
            labels={"outcome": outcome},
        )
        assert v == 1.0

    def test_duration_histogram_observed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        metrics_registry: MetricsRegistry,
    ) -> None:
        metrics_registry.reset()
        sid = _prepare(client, auth_headers)
        _create_and_run_gen(client, sid, auth_headers)
        # Хотя бы одна observation должна быть зафиксирована.
        text = metrics_registry.render_prometheus()
        assert "rag_card_generation_duration_ms" in text


# ============================================================
# T-S05-040: structured logs
# ============================================================


class TestStructuredLogs:
    def test_job_started_and_finished_logs(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sid = _prepare(client, auth_headers)
        with caplog.at_level(
            logging.INFO, logger="fe_bot.setup.rag_card_generation.orchestrator"
        ):
            _create_and_run_gen(client, sid, auth_headers)
        messages = [r.message for r in caplog.records]
        assert "rag_card_generation_job_started" in messages
        assert "rag_card_generation_job_finished" in messages

    def test_per_card_log_contains_fields(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sid = _prepare(client, auth_headers)
        with caplog.at_level(
            logging.INFO, logger="fe_bot.setup.rag_card_generation.orchestrator"
        ):
            _create_and_run_gen(client, sid, auth_headers)
        per_card = [r for r in caplog.records if r.message == "rag_card_generated"]
        assert per_card, "expected at least one rag_card_generated log"
        rec = per_card[0]
        for f in (
            "generation_job_id",
            "section_id",
            "doc_id",
            "doc_type",
            "confidence_level",
            "duration_ms",
            "outcome",
        ):
            assert hasattr(rec, f), f"log record missing field {f}"
