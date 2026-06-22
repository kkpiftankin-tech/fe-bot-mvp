"""Unit-тесты ConfidenceCalculator (SETUP-05 / T-S05-021)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.rag_card_generation_job_section import CardConfidenceLevel
from schemas.setup.rag_card_generation_report import CardValidationReportDTO

from fe_bot.setup.rag_card_generation.confidence_calculator import (
    ConfidenceCalculator,
)
from fe_bot.setup.rag_card_generation.llm_adapter import LLMGenerationResult
from fe_bot.setup.rag_card_generation.ontology_mapper import OntologyWarning
from fe_bot.setup.rag_card_generation.precheck import RAGCardDraft

pytestmark = pytest.mark.unit


def _draft() -> RAGCardDraft:
    return RAGCardDraft(
        doc_id="x.v1",
        doc_type="schema_card",
        title="X",
        body_markdown="body" * 10,
        front_matter={"doc_id": "x.v1", "doc_type": "schema_card"},
        source_files=["x.md"],
        source_sections=["sec_001"],
        retrieval_tags=["x"],
    )


def _precheck(*, passed: bool = True, n_errors: int = 0) -> CardValidationReportDTO:
    return CardValidationReportDTO(
        validation_report_id="val_001",
        doc_id="x.v1",
        card_version="1.0",
        passed=passed,
        errors=[{"code": f"E_{i}"} for i in range(n_errors)],
        warnings=[],
        checked_at=datetime(2026, 6, 19, tzinfo=UTC),
    )


def _llm_result(*, attempts: int = 1, used_fallback: bool = False) -> LLMGenerationResult:
    return LLMGenerationResult(
        draft=_draft(),
        attempts=attempts,
        duration_ms=100,
        model="llama3.2",
        used_fallback=used_fallback,
    )


def _ontology_warning(field: str = "domain") -> OntologyWarning:
    return OntologyWarning(
        field=field,
        raw_value="kitchen",
        code="ONTOLOGY_UNKNOWN_TERM",
        message=f"Unknown {field}",
    )


@pytest.fixture
def calc() -> ConfidenceCalculator:
    return ConfidenceCalculator()


class TestLevels:
    def test_high_when_clean(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(),
            ontology_warnings=[],
        )
        assert d.level == CardConfidenceLevel.HIGH
        assert d.score == 1.0
        assert d.reasons == []

    def test_medium_with_two_warnings(self, calc: ConfidenceCalculator) -> None:
        # 2 warnings * 0.15 = 0.3 penalty → score=0.7 → MEDIUM (0.6..0.85).
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(),
            ontology_warnings=[_ontology_warning(), _ontology_warning("phase")],
        )
        assert d.level == CardConfidenceLevel.MEDIUM
        assert 0.6 <= d.score < 0.85
        assert any("ontology" in r for r in d.reasons)

    def test_high_with_one_warning(self, calc: ConfidenceCalculator) -> None:
        # 1 warning * 0.15 = 0.15 → score=0.85 → HIGH (порог включительно).
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(),
            ontology_warnings=[_ontology_warning()],
        )
        assert d.level == CardConfidenceLevel.HIGH

    def test_medium_with_one_retry(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(attempts=2),
            ontology_warnings=[],
        )
        assert d.level == CardConfidenceLevel.MEDIUM

    def test_low_with_fallback(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(used_fallback=True),
            ontology_warnings=[],
        )
        assert d.level == CardConfidenceLevel.LOW
        assert "used_fallback_generator" in d.reasons

    def test_low_when_precheck_failed(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(passed=False, n_errors=2),
            llm_result=_llm_result(),
            ontology_warnings=[],
        )
        assert d.level == CardConfidenceLevel.LOW

    def test_low_with_many_warnings(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(),
            ontology_warnings=[_ontology_warning() for _ in range(5)],
        )
        assert d.level == CardConfidenceLevel.LOW


class TestReviewRequired:
    def test_high_no_review(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(),
            ontology_warnings=[],
        )
        assert calc.is_review_required(d, threshold=0.7) is False

    def test_low_review(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(used_fallback=True),
            ontology_warnings=[],
        )
        assert calc.is_review_required(d, threshold=0.7) is True

    def test_precheck_failed_forces_review(self, calc: ConfidenceCalculator) -> None:
        pr = _precheck(passed=False, n_errors=1)
        d = calc.calculate(
            precheck=pr,
            llm_result=_llm_result(),
            ontology_warnings=[],
        )
        # Даже если score выше threshold, precheck.passed=False → review.
        assert calc.is_review_required(d, threshold=0.0, precheck=pr) is True

    def test_threshold_boundary(self, calc: ConfidenceCalculator) -> None:
        d = calc.calculate(
            precheck=_precheck(),
            llm_result=_llm_result(attempts=2),  # -0.2 → score=0.8
            ontology_warnings=[],
        )
        # threshold=0.85 → review required.
        assert calc.is_review_required(d, threshold=0.85)
        # threshold=0.7 → не required.
        assert not calc.is_review_required(d, threshold=0.7)
