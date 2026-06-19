"""Unit-тесты RAGCardGenerationJobSection (SETUP-05 / T-S05-002)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.rag_card_generation_job_section import (
    CardConfidenceLevel,
    RAGCardGenerationJobSection,
    RAGCardGenerationJobSectionStatus,
)

pytestmark = pytest.mark.unit


def _section(**overrides: object) -> RAGCardGenerationJobSection:
    kwargs: dict[str, object] = {
        "generation_job_section_id": "gjs_001",
        "generation_job_id": "gen_001",
        "section_id": "sec_001",
        "source_document_id": "src_001",
    }
    kwargs.update(overrides)
    return RAGCardGenerationJobSection(**kwargs)


class TestBasics:
    def test_default_pending(self) -> None:
        assert _section().status == RAGCardGenerationJobSectionStatus.PENDING

    def test_five_statuses(self) -> None:
        assert {s.value for s in RAGCardGenerationJobSectionStatus} == {
            "pending",
            "processing",
            "completed",
            "failed",
            "skipped",
        }

    def test_confidence_levels(self) -> None:
        assert {c.value for c in CardConfidenceLevel} == {
            "high",
            "medium",
            "low",
        }


class TestValidators:
    def test_finished_before_started_raises(self) -> None:
        early = datetime(2026, 6, 19, 10, tzinfo=UTC)
        late = datetime(2026, 6, 19, 12, tzinfo=UTC)
        with pytest.raises(ValidationError):
            _section(started_at=late, finished_at=early)

    def test_valid_timing(self) -> None:
        early = datetime(2026, 6, 19, 10, tzinfo=UTC)
        late = datetime(2026, 6, 19, 12, tzinfo=UTC)
        sec = _section(started_at=early, finished_at=late, duration_ms=7200000)
        assert sec.duration_ms == 7200000

    def test_completed_section_has_doc_id(self) -> None:
        sec = _section(
            status=RAGCardGenerationJobSectionStatus.COMPLETED,
            target_doc_type="analytics_card",
            generated_doc_id="analytics.sensor.v1",
            confidence_level=CardConfidenceLevel.HIGH,
        )
        assert sec.generated_doc_id == "analytics.sensor.v1"
