"""Unit-тесты ConfidenceCalculator parser penalty (SETUP-12 / T-S12-053).

Покрывает только новую функциональность — penalty за parser
classification state.unknown_at_level. Существующие тесты
ConfidenceCalculator не трогаются.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.rag_card_generation_report import CardValidationReportDTO
from schemas.taxonomy.state import ClassificationState

from fe_bot.setup.rag_card_generation.confidence_calculator import (
    ConfidenceCalculator,
)
from fe_bot.setup.rag_card_generation.llm_adapter import LLMGenerationResult
from fe_bot.setup.rag_card_generation.precheck import RAGCardDraft

pytestmark = pytest.mark.unit


def _passed_precheck() -> CardValidationReportDTO:
    return CardValidationReportDTO(
        validation_report_id="val_x",
        doc_id="doc_x",
        card_version="1.0",
        passed=True,
        errors=[],
        warnings=[],
        checked_at=datetime.now(tz=UTC),
    )


def _llm_ok() -> LLMGenerationResult:
    return LLMGenerationResult(
        draft=RAGCardDraft(
            doc_id="x.v1",
            doc_type="schema_card",
            title="X",
            body_markdown="body text long enough for the precheck threshold.",
            front_matter={"doc_id": "x.v1", "doc_type": "schema_card"},
            source_files=["x.md"],
            source_sections=["sec_1"],
            retrieval_tags=["x"],
        ),
        attempts=1,
        duration_ms=10,
        model="llama3.2",
        used_fallback=False,
    )


class TestParserPenalty:
    def test_no_penalty_when_unknown_is_none(self) -> None:
        calc = ConfidenceCalculator()
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=None,
        )
        d = calc.calculate(
            precheck=_passed_precheck(),
            llm_result=_llm_ok(),
            ontology_warnings=[],
            parser_classification_state=state,
        )
        assert d.score == 1.0
        # reasons не содержит parser_unknown
        assert not any("parser_unknown" in r for r in d.reasons)

    def test_penalty_for_unknown_at_l1(self) -> None:
        calc = ConfidenceCalculator()
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=1,
        )
        d = calc.calculate(
            precheck=_passed_precheck(),
            llm_result=_llm_ok(),
            ontology_warnings=[],
            parser_classification_state=state,
        )
        assert d.score == pytest.approx(0.9)  # 1.0 - 0.1
        assert any("parser_unknown_at_level:1" in r for r in d.reasons)

    def test_penalty_for_unknown_at_l2(self) -> None:
        calc = ConfidenceCalculator()
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=2,
        )
        d = calc.calculate(
            precheck=_passed_precheck(),
            llm_result=_llm_ok(),
            ontology_warnings=[],
            parser_classification_state=state,
        )
        assert d.score == pytest.approx(0.95)  # 1.0 - 0.05
        assert any("parser_unknown_at_level:2" in r for r in d.reasons)

    def test_penalty_for_unknown_at_l0(self) -> None:
        calc = ConfidenceCalculator()
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            unknown_at_level=0,
        )
        d = calc.calculate(
            precheck=_passed_precheck(),
            llm_result=_llm_ok(),
            ontology_warnings=[],
            parser_classification_state=state,
        )
        assert d.score == pytest.approx(0.7)  # 1.0 - 0.3

    def test_backward_compat_without_state(self) -> None:
        """Без parser_classification_state — поведение как в SETUP-05."""
        calc = ConfidenceCalculator()
        d = calc.calculate(
            precheck=_passed_precheck(),
            llm_result=_llm_ok(),
            ontology_warnings=[],
        )
        assert d.score == 1.0
        assert d.reasons == []
