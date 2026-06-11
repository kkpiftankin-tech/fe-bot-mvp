"""Unit-тесты ProcessingLogRepository (T-S03-007)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.processing_log import (
    ProcessingLogLevel,
    ProcessingLogStep,
    SourceProcessingLogEntry,
)

from fe_bot.setup.source_registry.processing_log import (
    InMemoryProcessingLogRepository,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    log_id: str = "log_001",
    source_id: str = "src_001",
    job_id: str = "setup_001",
    step: ProcessingLogStep = ProcessingLogStep.PARSING,
    level: ProcessingLogLevel = ProcessingLogLevel.INFO,
    event_id: str = "evt_001",
    message: str = "ok",
) -> SourceProcessingLogEntry:
    return SourceProcessingLogEntry(
        processing_log_id=log_id,
        source_document_id=source_id,
        setup_job_id=job_id,
        step=step,
        level=level,
        message=message,
        event_id=event_id,
        created_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )


class TestAppendIdempotency:
    def test_append_stores(self) -> None:
        repo = InMemoryProcessingLogRepository()
        stored = repo.append(_entry())
        assert stored.event_id == "evt_001"

    def test_idempotent_by_event_id(self) -> None:
        repo = InMemoryProcessingLogRepository()
        first = repo.append(_entry())
        second = repo.append(
            _entry(log_id="log_DIFFERENT", event_id="evt_001", message="other")
        )
        assert second.processing_log_id == first.processing_log_id
        assert len(repo.list_for_document("src_001")) == 1


class TestFiltering:
    def test_filter_by_step(self) -> None:
        repo = InMemoryProcessingLogRepository()
        repo.append(_entry(log_id="l1", event_id="e1", step=ProcessingLogStep.PARSING))
        repo.append(
            _entry(log_id="l2", event_id="e2", step=ProcessingLogStep.RAG_CARD_GENERATION)
        )
        parsed = repo.list_for_document(
            "src_001", step=ProcessingLogStep.PARSING
        )
        assert len(parsed) == 1
        assert parsed[0].processing_log_id == "l1"

    def test_filter_by_level(self) -> None:
        repo = InMemoryProcessingLogRepository()
        repo.append(_entry(log_id="l1", event_id="e1", level=ProcessingLogLevel.INFO))
        repo.append(
            _entry(
                log_id="l2", event_id="e2", level=ProcessingLogLevel.ERROR,
                message="boom",
            )
        )
        errors = repo.list_for_document(
            "src_001", level=ProcessingLogLevel.ERROR
        )
        assert len(errors) == 1
        assert errors[0].message == "boom"

    def test_filter_by_step_and_level_combined(self) -> None:
        repo = InMemoryProcessingLogRepository()
        repo.append(
            _entry(
                log_id="l1", event_id="e1",
                step=ProcessingLogStep.PARSING, level=ProcessingLogLevel.ERROR
            )
        )
        repo.append(
            _entry(
                log_id="l2", event_id="e2",
                step=ProcessingLogStep.PARSING, level=ProcessingLogLevel.INFO
            )
        )
        repo.append(
            _entry(
                log_id="l3", event_id="e3",
                step=ProcessingLogStep.RAG_CARD_GENERATION,
                level=ProcessingLogLevel.ERROR,
            )
        )
        result = repo.list_for_document(
            "src_001",
            step=ProcessingLogStep.PARSING,
            level=ProcessingLogLevel.ERROR,
        )
        assert [r.processing_log_id for r in result] == ["l1"]


class TestJobScope:
    def test_list_for_job_aggregates_all_documents(self) -> None:
        repo = InMemoryProcessingLogRepository()
        repo.append(_entry(source_id="src_A", event_id="e1"))
        repo.append(_entry(source_id="src_B", event_id="e2"))
        repo.append(_entry(source_id="src_C", event_id="e3", job_id="setup_OTHER"))
        items = repo.list_for_job("setup_001")
        ids = sorted(i.source_document_id for i in items)
        assert ids == ["src_A", "src_B"]

    def test_list_for_job_filter_by_level(self) -> None:
        repo = InMemoryProcessingLogRepository()
        repo.append(_entry(source_id="src_A", event_id="e1"))
        repo.append(
            _entry(source_id="src_B", event_id="e2", level=ProcessingLogLevel.ERROR)
        )
        errors = repo.list_for_job("setup_001", level=ProcessingLogLevel.ERROR)
        assert len(errors) == 1
        assert errors[0].source_document_id == "src_B"
