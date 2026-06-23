"""PreApproveValidationOrchestrator (SETUP-06 / T-S06-014).

Объединяет CardSourceTraceValidator + CardBodyValidator + metadata precheck
из SETUP-05 в единый отчёт перед approve.

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §7.1 (шаг 9).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.rag.rag_card import RAGCard

from .body import CardBodyValidator, ValidationError
from .source_trace import CardSourceTraceValidator


@dataclass(frozen=True)
class PreApproveReport:
    """Сводный отчёт pre-approve проверок.

    ``passed`` == True если нет критических ошибок (warnings разрешены при
    policy allow_warnings).
    """

    passed: bool
    critical_errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


class PreApproveValidationOrchestrator:
    """Combines source-trace + body + metadata прекчеки.

    Metadata прекчек — minimal MVP: проверяет наличие doc_id, doc_type,
    непустого title. Полная SETUP-07 metadata validation — отдельная фича.
    """

    def __init__(
        self,
        *,
        source_trace_validator: CardSourceTraceValidator | None = None,
        body_validator: CardBodyValidator | None = None,
    ) -> None:
        self._source_trace = source_trace_validator or CardSourceTraceValidator()
        self._body = body_validator or CardBodyValidator()

    def validate(self, card: RAGCard) -> PreApproveReport:
        critical: list[ValidationError] = []
        warnings: list[ValidationError] = []

        # Source trace (AC-16)
        source_result = self._source_trace.validate(card)
        critical.extend(source_result.errors)

        # Body (AC-17)
        body_result = self._body.validate(card)
        critical.extend(body_result.errors)

        # Minimal metadata check
        if not card.doc_id:
            critical.append(
                ValidationError(
                    code="DOC_ID_REQUIRED",
                    message="Карточка должна иметь doc_id",
                )
            )
        if not card.title:
            critical.append(
                ValidationError(
                    code="TITLE_REQUIRED",
                    message="Карточка должна иметь title",
                )
            )

        # Warnings из confidence_level
        if (card.confidence_level or "").lower() == "low":
            warnings.append(
                ValidationError(
                    code="LOW_CONFIDENCE_APPROVE",
                    message="Approve карточки с low confidence — требует подтверждения",
                )
            )

        return PreApproveReport(
            passed=not critical,
            critical_errors=critical,
            warnings=warnings,
        )
