"""Unit-тесты DocumentParseReportRepository (T-S04-009)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.parse_job_document import ParseJobDocumentStatus
from schemas.setup.parse_report import DocumentParseReport, SectionsSummary

from fe_bot.setup.parser.report_repository import (
    InMemoryDocumentParseReportRepository,
    ParseReportNotFoundError,
)

pytestmark = pytest.mark.unit


def _report(
    *,
    parse_report_id: str = "rep_001",
    parse_job_id: str = "pj_001",
    source_document_id: str = "src_001",
    status: ParseJobDocumentStatus = ParseJobDocumentStatus.COMPLETED,
    sections_count: int = 3,
) -> DocumentParseReport:
    return DocumentParseReport(
        parse_report_id=parse_report_id,
        parse_job_id=parse_job_id,
        source_document_id=source_document_id,
        status=status,
        summary=SectionsSummary(
            sections_count=sections_count,
            sections_by_type={},
            low_confidence_sections=0,
        ),
        created_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
    )


class TestBasics:
    def test_save_and_get(self) -> None:
        repo = InMemoryDocumentParseReportRepository()
        repo.save(_report())
        assert repo.get("rep_001").summary.sections_count == 3

    def test_get_unknown_raises(self) -> None:
        repo = InMemoryDocumentParseReportRepository()
        with pytest.raises(ParseReportNotFoundError):
            repo.get("nope")


class TestLookupByPair:
    def test_get_for_document_in_job(self) -> None:
        repo = InMemoryDocumentParseReportRepository()
        repo.save(_report())
        found = repo.get_for_document_in_job("pj_001", "src_001")
        assert found is not None
        assert found.parse_report_id == "rep_001"

    def test_get_for_document_in_job_none(self) -> None:
        repo = InMemoryDocumentParseReportRepository()
        assert repo.get_for_document_in_job("pj_001", "src_001") is None

    def test_save_overwrite_same_pair_keeps_latest(self) -> None:
        """Повторный save для (pj, doc) — last-write-wins."""
        repo = InMemoryDocumentParseReportRepository()
        repo.save(_report(parse_report_id="rep_old", sections_count=3))
        repo.save(_report(parse_report_id="rep_new", sections_count=5))
        found = repo.get_for_document_in_job("pj_001", "src_001")
        assert found is not None
        assert found.parse_report_id == "rep_new"
        assert found.summary.sections_count == 5
        # Старый rep_old удалён из основного индекса.
        with pytest.raises(ParseReportNotFoundError):
            repo.get("rep_old")


class TestListing:
    def test_list_for_job(self) -> None:
        repo = InMemoryDocumentParseReportRepository()
        repo.save(_report(parse_report_id="r1", source_document_id="src_A"))
        repo.save(_report(parse_report_id="r2", source_document_id="src_B"))
        repo.save(
            _report(
                parse_report_id="r3",
                parse_job_id="other",
                source_document_id="src_C",
            )
        )
        items = repo.list_for_job("pj_001")
        assert {r.parse_report_id for r in items} == {"r1", "r2"}
