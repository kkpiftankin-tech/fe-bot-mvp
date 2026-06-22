"""ConfidenceCalculator (SETUP-05 / T-S05-021).

Считает итоговый ``confidence_level`` (high/medium/low) для RAGCardDraft на основе:
- precheck: passed (без errors) или нет.
- ontology warnings count.
- LLM attempts (1 attempt → высокий, >=2 attempts → понижение).
- used_fallback: всегда low.

Подход — взвешенный счёт от 1.0 вниз. Threshold:
- ``high`` (>= 0.85): чистый precheck, 0 ontology warnings, 1 attempt, не fallback.
- ``medium`` (0.6..0.85): одно отклонение (1 warning или retry).
- ``low`` (< 0.6): >= 2 ontology warnings, fallback, precheck failed.

``is_review_required(decision, threshold)`` возвращает True если score < threshold
ИЛИ precheck failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.setup.rag_card_generation_job_section import CardConfidenceLevel
from schemas.setup.rag_card_generation_report import CardValidationReportDTO

from fe_bot.setup.rag_card_generation.llm_adapter import LLMGenerationResult
from fe_bot.setup.rag_card_generation.ontology_mapper import OntologyWarning

_HIGH_THRESHOLD = 0.85
_MEDIUM_THRESHOLD = 0.6

# Штрафы за каждый фактор (вычитаются из 1.0).
_PENALTY_PRECHECK_FAILED = 0.5
_PENALTY_PER_ONTOLOGY_WARNING = 0.15
_PENALTY_PER_EXTRA_ATTEMPT = 0.2
_PENALTY_FALLBACK = 0.5


@dataclass(slots=True)
class ConfidenceDecision:
    """Результат calculate(): уровень + score + список причин."""

    level: CardConfidenceLevel
    score: float
    reasons: list[str] = field(default_factory=list)


class ConfidenceCalculator:
    """Stateless calculator на основе precheck + ontology + LLM attempts."""

    def calculate(
        self,
        *,
        precheck: CardValidationReportDTO,
        llm_result: LLMGenerationResult,
        ontology_warnings: list[OntologyWarning],
    ) -> ConfidenceDecision:
        score = 1.0
        reasons: list[str] = []

        if not precheck.passed:
            score -= _PENALTY_PRECHECK_FAILED
            reasons.append(f"precheck_failed:{len(precheck.errors)}_errors")

        warning_count = len(ontology_warnings)
        if warning_count > 0:
            penalty = warning_count * _PENALTY_PER_ONTOLOGY_WARNING
            score -= penalty
            reasons.append(f"ontology_warnings:{warning_count}")

        extra_attempts = max(llm_result.attempts - 1, 0)
        if extra_attempts > 0:
            penalty = extra_attempts * _PENALTY_PER_EXTRA_ATTEMPT
            score -= penalty
            reasons.append(f"llm_extra_attempts:{extra_attempts}")

        if llm_result.used_fallback:
            score -= _PENALTY_FALLBACK
            reasons.append("used_fallback_generator")

        score = max(0.0, min(1.0, score))

        if score >= _HIGH_THRESHOLD:
            level = CardConfidenceLevel.HIGH
        elif score >= _MEDIUM_THRESHOLD:
            level = CardConfidenceLevel.MEDIUM
        else:
            level = CardConfidenceLevel.LOW

        return ConfidenceDecision(level=level, score=score, reasons=reasons)

    @staticmethod
    def is_review_required(
        decision: ConfidenceDecision,
        *,
        threshold: float = 0.7,
        precheck: CardValidationReportDTO | None = None,
    ) -> bool:
        """True если score < threshold ИЛИ precheck не прошёл."""
        if precheck is not None and not precheck.passed:
            return True
        return decision.score < threshold
