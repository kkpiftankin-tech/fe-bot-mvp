"""Unit-тесты CardGenerationReport + CardValidationReport (SETUP-05 / T-S05-006)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.rag_card_generation_job import RAGCardGenerationJobStatus
from schemas.setup.rag_card_generation_report import (
    CardGenerationReportDTO,
    CardGenerationSummary,
    CardValidationReportDTO,
)

pytestmark = pytest.mark.unit


class TestGenerationReport:
    def test_minimal(self) -> None:
        report = CardGenerationReportDTO(
            generation_report_id="rep_001",
            generation_job_id="gen_001",
            status=RAGCardGenerationJobStatus.COMPLETED,
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
        assert report.summary.total_sections == 0
        assert report.errors == []
        assert report.warnings == []

    def test_with_summary(self) -> None:
        report = CardGenerationReportDTO(
            generation_report_id="rep_001",
            generation_job_id="gen_001",
            status=RAGCardGenerationJobStatus.PARTIAL_SUCCESS,
            summary=CardGenerationSummary(
                total_sections=10,
                processed_sections=8,
                generated_cards=7,
                failed_sections=1,
                review_required_cards=3,
                cards_by_type={
                    "analytics_card": 3,
                    "schema_card": 2,
                    "task_card": 2,
                },
            ),
            errors=[{"code": "INVALID_LLM_OUTPUT", "section_id": "sec_005"}],
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
        assert report.summary.generated_cards == 7
        assert report.summary.cards_by_type["analytics_card"] == 3

    def test_frozen(self) -> None:
        report = CardGenerationReportDTO(
            generation_report_id="rep_001",
            generation_job_id="gen_001",
            status=RAGCardGenerationJobStatus.COMPLETED,
            created_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
        with pytest.raises(ValidationError):
            report.generation_job_id = "another"  # type: ignore[misc]


class TestValidationReport:
    def test_passed(self) -> None:
        rep = CardValidationReportDTO(
            validation_report_id="val_001",
            doc_id="analytics.x.v1",
            card_version="1.0",
            passed=True,
            checked_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
        assert rep.passed
        assert rep.errors == []

    def test_with_errors(self) -> None:
        rep = CardValidationReportDTO(
            validation_report_id="val_001",
            doc_id="analytics.x.v1",
            card_version="1.0",
            passed=False,
            errors=[
                {"code": "DOC_ID_MISSING", "field": "doc_id"},
                {"code": "CARD_BODY_EMPTY", "field": "body_markdown"},
            ],
            warnings=[{"code": "RETRIEVAL_TAGS_EMPTY"}],
            checked_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
        assert len(rep.errors) == 2
        assert rep.errors[0]["code"] == "DOC_ID_MISSING"

    def test_frozen(self) -> None:
        rep = CardValidationReportDTO(
            validation_report_id="val_001",
            doc_id="x",
            card_version="1.0",
            passed=True,
            checked_at=datetime(2026, 6, 19, tzinfo=UTC),
        )
        with pytest.raises(ValidationError):
            rep.passed = False  # type: ignore[misc]
