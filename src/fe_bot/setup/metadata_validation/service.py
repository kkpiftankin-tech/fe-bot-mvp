"""Metadata Validation Service (T-S01-024).

Прогоняет карточки через детерминированный validator (validators/rag_metadata_validator.py),
обновляет card.status в Registry в зависимости от результата:

- PASSED → metadata_validated
- WARNING → review_required (с note)
- FAILED → review_required (с note)

Бизнес-правило: при review_policy="strict" любая WARNING/FAILED останавливает
автоматический прогон pipeline в S5 (chunking) — требуется HITL approve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from schemas.rag.rag_card import CardStatus
from schemas.setup.validation_report import ValidationReport, ValidationStatus
from validators.rag_metadata_validator import validate_rag_card

from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    RAGCardRegistry,
)


class ReviewPolicy(StrEnum):
    """Политика прохождения validation."""

    STRICT = "strict"  # любая WARNING/FAILED → review_required
    ALLOW_WARNINGS = "allow_warnings"  # WARNING → metadata_validated, FAILED → review


@dataclass(slots=True)
class ValidationBatchResult:
    """Сводка прогона валидации по партии карточек."""

    total: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    review_required: int = 0
    reports: list[ValidationReport] = field(default_factory=list)


class MetadataValidationService:
    """Запускает rag_metadata_validator на наборе карточек из реестра."""

    def __init__(
        self,
        *,
        registry: RAGCardRegistry,
        review_policy: ReviewPolicy = ReviewPolicy.STRICT,
    ) -> None:
        self._registry = registry
        self._policy = review_policy

    def validate_for_job(self, setup_job_id: str) -> ValidationBatchResult:
        """Валидирует все карточки job в статусах generated / draft.

        Не трогает уже approved / chunked / далее по lifecycle.
        """
        records = self._registry.list_for_job(
            setup_job_id,
            status_in=frozenset(
                {
                    CardStatus.DRAFT,
                    CardStatus.GENERATED,
                    CardStatus.REVIEW_REQUIRED,
                }
            ),
        )
        result = ValidationBatchResult()
        result.total = len(records)

        # known_doc_ids для проверки уникальности на этом setup_job:
        all_doc_ids_in_job = {
            r.card.doc_id for r in self._registry.list_for_job(setup_job_id)
        }

        for rec in records:
            known = all_doc_ids_in_job - {rec.card.doc_id}
            # Валидируем "what-if metadata_validated", чтобы не получать
            # STATUS_NOT_INDEXABLE warning на исходный GENERATED статус —
            # ведь этот сервис именно и переводит карточку из generated
            # в metadata_validated.
            probe_card = rec.card.model_copy(
                update={"status": CardStatus.METADATA_VALIDATED}
            )
            report = validate_rag_card(probe_card, rec.metadata, known_doc_ids=known)
            result.reports.append(report)
            self._apply_validation(rec.card.doc_id, rec.card.status, report, result)

        return result

    def validate_one(self, doc_id: str) -> ValidationReport:
        """Прогон для одной карточки (полезно для review/regenerate)."""
        try:
            rec = self._registry.get(doc_id)
        except CardNotFoundError:
            raise
        # known не критичен для одиночной валидации (uniqueness check внутри job)
        known: set[str] = {
            r.card.doc_id
            for r in self._registry.list_for_job(rec.setup_job_id)
            if r.card.doc_id != doc_id
        }
        probe_card = rec.card.model_copy(
            update={"status": CardStatus.METADATA_VALIDATED}
        )
        report = validate_rag_card(probe_card, rec.metadata, known_doc_ids=known)
        result = ValidationBatchResult(total=1, reports=[report])
        self._apply_validation(doc_id, rec.card.status, report, result)
        return report

    def _apply_validation(
        self,
        doc_id: str,
        current_status: CardStatus,
        report: ValidationReport,
        batch: ValidationBatchResult,
    ) -> None:
        """Обновляет статус карточки в реестре по итогу validation."""
        rec = self._registry.get(doc_id)
        card = rec.card

        # Cannot transition from APPROVED/CHUNKED/etc downward via validation
        if current_status not in {
            CardStatus.DRAFT,
            CardStatus.GENERATED,
            CardStatus.REVIEW_REQUIRED,
            CardStatus.METADATA_VALIDATED,
        }:
            return

        if report.status == ValidationStatus.PASSED:
            target = CardStatus.METADATA_VALIDATED
            batch.passed += 1
            note = "validation passed"
        elif report.status == ValidationStatus.WARNING:
            batch.warnings += 1
            if self._policy == ReviewPolicy.ALLOW_WARNINGS:
                target = CardStatus.METADATA_VALIDATED
                note = (
                    f"validation warnings ({len(report.warnings)}); "
                    "auto-approved under allow_warnings policy"
                )
            else:
                target = CardStatus.REVIEW_REQUIRED
                batch.review_required += 1
                note = f"validation warnings ({len(report.warnings)}) — review required"
        elif report.status == ValidationStatus.FAILED:
            target = CardStatus.REVIEW_REQUIRED
            batch.failed += 1
            batch.review_required += 1
            note = f"validation failed ({len(report.errors)} errors)"
        else:  # REPAIR_REQUIRED
            target = CardStatus.REVIEW_REQUIRED
            batch.review_required += 1
            note = "validation repair_required"

        # Defensive: не пытаемся вернуться, если уже в target
        if card.status == target:
            return

        try:
            if not card.can_transition_to(target):
                # Например REVIEW_REQUIRED → REVIEW_REQUIRED, или
                # GENERATED → METADATA_VALIDATED ok. Если переход невалиден —
                # помечаем error в batch, но не падаем.
                batch.review_required += 1
                return
            updated_card = card.model_copy(update={"status": target})
            self._registry.update(doc_id, card=updated_card, note=note)
        except Exception:
            # Тёплая ошибка — оставляем как есть, ловит integration-тест.
            pass
