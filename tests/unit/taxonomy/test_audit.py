"""Unit-тесты TaxonomyAuditEmitter (SETUP-12 / T-S12-102)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.registry import TaxonomyBitRegistryEntry
from schemas.taxonomy.state import AutoCreationRecord

from fe_bot.audit.service import (
    AuditAction,
    AuditOutcome,
    AuditService,
    InMemoryAuditLog,
)
from fe_bot.taxonomy import (
    AllocationResult,
    AllocationSource,
    TaxonomyAuditEmitter,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    level: int = 1,
    parent_path: str = "task",
    bit_index: int = 0,
    class_slug: str = "pvo",
) -> TaxonomyBitRegistryEntry:
    return TaxonomyBitRegistryEntry(
        version_id="v1.0.0",
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=f"Класс {class_slug}",
        description=f"Описание {class_slug}.",
        created_at=datetime.now(tz=UTC),
    )


def _record(
    *,
    level: int = 1,
    parent_path: str = "task",
    bit_index: int = 0,
    class_slug: str = "pvo",
) -> AutoCreationRecord:
    return AutoCreationRecord(
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        triggered_by_section_id="sec_1",
        created_at=datetime.now(tz=UTC),
    )


def _result(
    *,
    source: AllocationSource = AllocationSource.AUTO_CREATE,
    entry: TaxonomyBitRegistryEntry | None = None,
    record: AutoCreationRecord | None = None,
    similarity: float | None = None,
    closest_slug: str | None = None,
    warning: str | None = None,
) -> AllocationResult:
    e = entry or _entry()
    return AllocationResult(
        bit_index=e.bit_index,
        source=source,
        target_entry=e,
        similarity_to_closest=similarity,
        closest_existing_slug=closest_slug,
        auto_creation_record=(
            record if source == AllocationSource.AUTO_CREATE else None
        ),
        warning_message=warning,
    )


def _make_audit() -> tuple[TaxonomyAuditEmitter, AuditService, InMemoryAuditLog]:
    log = InMemoryAuditLog()
    svc = AuditService(log)
    em = TaxonomyAuditEmitter(svc)
    return em, svc, log


class TestSkipForNonInterestingSources:
    def test_slug_match_skipped(self) -> None:
        em, _svc, log = _make_audit()
        em.emit_allocation(
            _result(source=AllocationSource.SLUG_MATCH),
            triggered_by_section_id="sec_1",
        )
        assert log.count() == 0

    def test_similarity_reuse_skipped(self) -> None:
        em, _svc, log = _make_audit()
        em.emit_allocation(
            _result(source=AllocationSource.SIMILARITY_REUSE),
            triggered_by_section_id="sec_1",
        )
        assert log.count() == 0


class TestAutoCreateAudit:
    def test_emits_event(self) -> None:
        em, _svc, log = _make_audit()
        result = _result(
            source=AllocationSource.AUTO_CREATE,
            record=_record(),
            similarity=0.45,
            closest_slug="navigation",
        )
        em.emit_allocation(result, triggered_by_section_id="sec_1")
        assert log.count() == 1
        event = log.list_recent(limit=1)[0]
        assert event.action == AuditAction.TAXONOMY_CLASS_AUTO_CREATED
        assert event.outcome == AuditOutcome.SUCCESS
        assert event.target_type == "taxonomy_class"
        assert event.target_id == "v1.0.0:1:task:0"
        assert event.payload["class_slug"] == "pvo"
        assert event.payload["similarity_to_closest"] == 0.45
        assert event.payload["closest_existing_slug"] == "navigation"
        assert event.payload["source"] == "auto_create"


class TestForceMergeAudit:
    def test_emits_event_with_failure_outcome(self) -> None:
        em, _svc, log = _make_audit()
        result = _result(
            source=AllocationSource.FORCE_MERGE,
            similarity=0.75,
            closest_slug="pvo",
            warning="overflow at task L1",
        )
        em.emit_allocation(result, triggered_by_section_id="sec_2")
        event = log.list_recent(limit=1)[0]
        assert event.action == AuditAction.TAXONOMY_CLASS_FORCE_MERGED
        assert event.outcome == AuditOutcome.FAILURE
        assert event.payload["warning_message"] == "overflow at task L1"


class TestOverflowAudit:
    def test_emits_event(self) -> None:
        em, _svc, log = _make_audit()
        result = _result(
            source=AllocationSource.CLASS_OVERFLOW,
            similarity=0.1,
            closest_slug="pvo",
            warning="no similar neighbour",
        )
        em.emit_allocation(result, triggered_by_section_id="sec_3")
        event = log.list_recent(limit=1)[0]
        assert event.action == AuditAction.TAXONOMY_CLASS_OVERFLOW
        assert event.outcome == AuditOutcome.FAILURE


class TestSetupJobIdPropagation:
    def test_setup_job_id_recorded(self) -> None:
        em, _svc, log = _make_audit()
        result = _result(source=AllocationSource.AUTO_CREATE, record=_record())
        em.emit_allocation(
            result,
            triggered_by_section_id="sec_x",
            setup_job_id="setup_abc",
        )
        event = log.list_recent(limit=1)[0]
        assert event.setup_job_id == "setup_abc"


class TestActorId:
    def test_default_actor(self) -> None:
        em, _svc, log = _make_audit()
        em.emit_allocation(
            _result(record=_record()), triggered_by_section_id="sec_x"
        )
        event = log.list_recent(limit=1)[0]
        assert event.actor_id == "taxonomy_auto_allocator"

    def test_custom_actor(self) -> None:
        log = InMemoryAuditLog()
        svc = AuditService(log)
        em = TaxonomyAuditEmitter(svc, actor_id="cron:hourly_drift_check")
        em.emit_allocation(
            _result(record=_record()), triggered_by_section_id="sec_x"
        )
        event = log.list_recent(limit=1)[0]
        assert event.actor_id == "cron:hourly_drift_check"
