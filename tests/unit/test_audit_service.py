"""Тесты Audit Service (T-S01-048)."""

from __future__ import annotations

import pytest

from fe_bot.audit.service import (
    AuditAction,
    AuditOutcome,
    AuditService,
    InMemoryAuditLog,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def log() -> InMemoryAuditLog:
    return InMemoryAuditLog()


@pytest.fixture
def svc(log: InMemoryAuditLog) -> AuditService:
    return AuditService(log)


class TestRecord:
    def test_record_creates_event(
        self, svc: AuditService, log: InMemoryAuditLog
    ) -> None:
        event = svc.record(
            actor_id="u1",
            action=AuditAction.JOB_CREATED,
            target_type="setup_job",
            target_id="setup_xyz",
            setup_job_id="setup_xyz",
            payload={"project_name": "Demo"},
        )
        assert event.event_id.startswith("aud_")
        assert event.actor_id == "u1"
        assert event.outcome == AuditOutcome.SUCCESS
        assert event.payload == {"project_name": "Demo"}
        assert log.count() == 1

    def test_event_is_frozen(self, svc: AuditService) -> None:
        event = svc.record(
            actor_id="u1",
            action=AuditAction.JOB_CREATED,
            target_type="setup_job",
            target_id="x",
        )
        with pytest.raises((TypeError, ValueError)):
            event.actor_id = "u2"  # type: ignore[misc]

    def test_extra_field_rejected(self) -> None:
        from fe_bot.audit.service import AuditEvent

        with pytest.raises(ValueError, match="extra"):
            AuditEvent(
                actor_id="u1",
                action=AuditAction.JOB_CREATED,
                target_type="setup_job",
                target_id="x",
                rogue_field="should fail",  # type: ignore[call-arg]
            )

    def test_outcome_failure(self, svc: AuditService) -> None:
        event = svc.record(
            actor_id="u1",
            action=AuditAction.PIPELINE_STEP_FAILED,
            target_type="setup_job",
            target_id="setup_xyz",
            outcome=AuditOutcome.FAILURE,
            payload={"step": "embedding", "error": "ollama down"},
        )
        assert event.outcome == AuditOutcome.FAILURE


class TestQuery:
    def test_list_for_job_filters(
        self, svc: AuditService, log: InMemoryAuditLog
    ) -> None:
        svc.record(
            actor_id="u1",
            action=AuditAction.JOB_CREATED,
            target_type="setup_job",
            target_id="a",
            setup_job_id="a",
        )
        svc.record(
            actor_id="u1",
            action=AuditAction.JOB_CREATED,
            target_type="setup_job",
            target_id="b",
            setup_job_id="b",
        )
        svc.record(
            actor_id="u2",
            action=AuditAction.CARD_REVIEW_APPROVED,
            target_type="rag_card",
            target_id="card1",
            setup_job_id="a",
        )

        a_events = log.list_for_job("a")
        assert len(a_events) == 2
        b_events = log.list_for_job("b")
        assert len(b_events) == 1

    def test_list_for_actor_filters(
        self, svc: AuditService, log: InMemoryAuditLog
    ) -> None:
        svc.record(
            actor_id="alice",
            action=AuditAction.CARD_REVIEW_APPROVED,
            target_type="rag_card",
            target_id="card1",
        )
        svc.record(
            actor_id="bob",
            action=AuditAction.CARD_REVIEW_REJECTED,
            target_type="rag_card",
            target_id="card2",
        )
        assert len(log.list_for_actor("alice")) == 1
        assert log.list_for_actor("alice")[0].action == AuditAction.CARD_REVIEW_APPROVED

    def test_list_recent_returns_newest_first(
        self, svc: AuditService, log: InMemoryAuditLog
    ) -> None:
        for i in range(5):
            svc.record(
                actor_id="u1",
                action=AuditAction.JOB_CREATED,
                target_type="setup_job",
                target_id=f"j{i}",
            )
        recent = log.list_recent(limit=3)
        assert len(recent) == 3
        # newest first
        assert recent[0].target_id == "j4"
        assert recent[2].target_id == "j2"


class TestImmutability:
    def test_returned_events_are_copies(
        self, svc: AuditService, log: InMemoryAuditLog
    ) -> None:
        svc.record(
            actor_id="u1",
            action=AuditAction.JOB_CREATED,
            target_type="setup_job",
            target_id="x",
            setup_job_id="x",
            payload={"k": "v"},
        )
        fetched = log.list_for_job("x")[0]
        # mutate payload-copy: оригинал не должен задеваться
        fetched.payload["new"] = "data"  # type: ignore[index]
        assert "new" not in log.list_for_job("x")[0].payload
