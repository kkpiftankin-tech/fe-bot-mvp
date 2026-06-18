"""Unit-тесты ProcessingLog DTO (T-S03-003)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.processing_log import (
    ProcessingLogLevel,
    ProcessingLogStep,
    SourceProcessingLogDTO,
    SourceProcessingLogEntry,
)

pytestmark = pytest.mark.unit


def _make_entry(**overrides: object) -> SourceProcessingLogEntry:
    defaults: dict[str, object] = {
        "processing_log_id": "log_001",
        "source_document_id": "src_001",
        "setup_job_id": "setup_001",
        "step": ProcessingLogStep.PARSING,
        "level": ProcessingLogLevel.INFO,
        "message": "Markdown parser started",
        "event_id": "evt_001",
        "created_at": datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
        "payload": {},
    }
    defaults.update(overrides)
    return SourceProcessingLogEntry(**defaults)  # type: ignore[arg-type]


class TestProcessingLogEntry:
    def test_valid_minimal(self) -> None:
        entry = _make_entry()
        assert entry.step == ProcessingLogStep.PARSING
        assert entry.level == ProcessingLogLevel.INFO
        assert entry.error_code is None

    def test_error_entry_has_error_code(self) -> None:
        entry = _make_entry(
            level=ProcessingLogLevel.ERROR,
            error_code="PARSE_TIMEOUT",
            message="Parser exceeded 60s timeout",
        )
        assert entry.error_code == "PARSE_TIMEOUT"
        assert entry.level == ProcessingLogLevel.ERROR

    def test_message_max_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_entry(message="x" * 4001)

    def test_message_min_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_entry(message="")

    def test_frozen_after_creation(self) -> None:
        entry = _make_entry()
        with pytest.raises(ValidationError):
            entry.message = "modified"  # type: ignore[misc]

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            _make_entry(extra_field="x")

    def test_payload_with_arbitrary_data(self) -> None:
        entry = _make_entry(payload={"parser_version": "1.0", "input_size_bytes": 1024})
        assert entry.payload["parser_version"] == "1.0"


class TestProcessingLogLevel:
    def test_all_levels(self) -> None:
        assert {lvl.value for lvl in ProcessingLogLevel} == {
            "debug",
            "info",
            "warning",
            "error",
        }


class TestProcessingLogStep:
    def test_all_steps(self) -> None:
        """13 шагов pipeline."""
        steps = {s.value for s in ProcessingLogStep}
        assert "upload" in steps
        assert "parsing" in steps
        assert "rag_card_generation" in steps
        assert "indexing" in steps
        assert "retry" in steps  # T-S03-021
        assert len(steps) == 13


class TestProcessingLogDTO:
    def test_empty_log(self) -> None:
        dto = SourceProcessingLogDTO(source_document_id="src_001")
        assert dto.items == []
        assert dto.total == 0

    def test_with_entries(self) -> None:
        dto = SourceProcessingLogDTO(
            source_document_id="src_001",
            items=[_make_entry()],
            total=1,
            page=1,
            page_size=50,
        )
        assert len(dto.items) == 1
