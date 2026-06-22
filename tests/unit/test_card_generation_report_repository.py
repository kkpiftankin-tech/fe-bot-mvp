"""Unit-тесты CardGenerationReportRepository (SETUP-05 / T-S05-012)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.rag_card_generation_job import RAGCardGenerationJobStatus
from schemas.setup.rag_card_generation_report import (
    CardGenerationReportDTO,
    CardGenerationSummary,
)

from fe_bot.setup.rag_card_generation.report_repository import (
    CardGenerationReportNotFoundError,
    InMemoryCardGenerationReportRepository,
)

pytestmark = pytest.mark.unit


def _report(
    *,
    generation_report_id: str = "rep_001",
    generation_job_id: str = "gen_001",
    status: RAGCardGenerationJobStatus = RAGCardGenerationJobStatus.COMPLETED,
    generated_cards: int = 5,
) -> CardGenerationReportDTO:
    return CardGenerationReportDTO(
        generation_report_id=generation_report_id,
        generation_job_id=generation_job_id,
        status=status,
        summary=CardGenerationSummary(
            total_sections=10,
            processed_sections=10,
            generated_cards=generated_cards,
            failed_sections=10 - generated_cards,
            review_required_cards=0,
            cards_by_type={"task_card": generated_cards},
        ),
        errors=[],
        warnings=[],
        created_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


class TestSaveGet:
    def test_save_and_get(self) -> None:
        repo = InMemoryCardGenerationReportRepository()
        repo.save(_report())
        loaded = repo.get("rep_001")
        assert loaded.summary.generated_cards == 5

    def test_get_unknown_raises(self) -> None:
        repo = InMemoryCardGenerationReportRepository()
        with pytest.raises(CardGenerationReportNotFoundError):
            repo.get("ghost")

    def test_get_for_job(self) -> None:
        repo = InMemoryCardGenerationReportRepository()
        repo.save(_report())
        report = repo.get_for_job("gen_001")
        assert report is not None
        assert report.generation_report_id == "rep_001"

    def test_get_for_job_missing_returns_none(self) -> None:
        repo = InMemoryCardGenerationReportRepository()
        assert repo.get_for_job("missing") is None


class TestLastWriteWins:
    def test_overwrites_per_job(self) -> None:
        repo = InMemoryCardGenerationReportRepository()
        repo.save(_report(generation_report_id="rep_a", generated_cards=3))
        repo.save(_report(generation_report_id="rep_b", generated_cards=7))
        # Old rep_a удалён, остался rep_b.
        with pytest.raises(CardGenerationReportNotFoundError):
            repo.get("rep_a")
        latest = repo.get_for_job("gen_001")
        assert latest is not None
        assert latest.generation_report_id == "rep_b"
        assert latest.summary.generated_cards == 7


class TestSnapshot:
    def test_roundtrip(self) -> None:
        repo = InMemoryCardGenerationReportRepository()
        repo.save(_report())
        snap = repo.snapshot()
        repo2 = InMemoryCardGenerationReportRepository()
        repo2.restore(snap)
        assert repo2.get_for_job("gen_001") is not None
