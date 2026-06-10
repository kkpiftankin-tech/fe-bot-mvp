"""Детерминированный валидатор RAG-карточек.

Реализует правила из docs/06-rag/rag-quality.md §1.1 и docs/06-rag/metadata-schema.md.
Используется на этапе SETUP-07 (metadata validation).

T-S01-005 acceptance: возвращает ValidationReportDTO с errors[], warnings[],
repair_instruction. Покрытие веток ≥ 90%.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from pydantic import ValidationError
from schemas.rag.ontology import (
    KNOWN_AGENTS,
    ConfidenceLevel,
    DocType,
    Phase,
)
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata
from schemas.setup.validation_report import (
    ValidationCheck,
    ValidationIssue,
    ValidationIssueSeverity,
    ValidationReport,
    ValidationStatus,
    ValidationTargetType,
)

VALIDATOR_NAME = "rag_metadata_validator"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _make_issue(
    code: str,
    message: str,
    field: str | None = None,
    severity: ValidationIssueSeverity = ValidationIssueSeverity.ERROR,
) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, field=field, severity=severity)


def validate_rag_card(
    card: RAGCard,
    metadata: RAGMetadata,
    *,
    known_doc_ids: Iterable[str] = (),
) -> ValidationReport:
    """Валидирует RAG-карточку и её metadata.

    Args:
        card: RAG-карточка.
        metadata: соответствующий RAGMetadata.
        known_doc_ids: doc_id-ы уже существующих карточек (для проверки уникальности).
            Если карточка ещё не сохранена — её doc_id не должен присутствовать
            в этом множестве.

    Returns:
        ValidationReport с errors/warnings и repair_instruction.
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    checks: list[ValidationCheck] = []

    # check 1: doc_id согласован между card и metadata
    doc_id_match = card.doc_id == metadata.doc_id
    checks.append(ValidationCheck(name="doc_id_consistency", passed=doc_id_match))
    if not doc_id_match:
        errors.append(
            _make_issue(
                code="DOC_ID_MISMATCH",
                field="doc_id",
                message=(
                    f"Card doc_id {card.doc_id!r} differs from metadata doc_id "
                    f"{metadata.doc_id!r}"
                ),
            )
        )

    # check 2: doc_type согласован
    doc_type_match = card.doc_type == metadata.doc_type
    checks.append(ValidationCheck(name="doc_type_consistency", passed=doc_type_match))
    if not doc_type_match:
        errors.append(
            _make_issue(
                code="DOC_TYPE_MISMATCH",
                field="doc_type",
                message=(
                    f"Card doc_type {card.doc_type.value!r} differs from metadata "
                    f"doc_type {metadata.doc_type.value!r}"
                ),
            )
        )

    # check 3: doc_id уникален
    is_unique = card.doc_id not in set(known_doc_ids)
    checks.append(ValidationCheck(name="doc_id_uniqueness", passed=is_unique))
    if not is_unique:
        errors.append(
            _make_issue(
                code="DOC_ID_DUPLICATE",
                field="doc_id",
                message=f"doc_id {card.doc_id!r} already exists in registry",
            )
        )

    # check 4: doc_type ∈ онтологии (тип уже enum, но проверим явно)
    doc_type_valid = isinstance(card.doc_type, DocType)
    checks.append(ValidationCheck(name="doc_type_in_ontology", passed=doc_type_valid))

    # check 5: retrieval_tags не пуст
    tags_nonempty = len(metadata.retrieval_tags) > 0
    checks.append(ValidationCheck(name="retrieval_tags_nonempty", passed=tags_nonempty))
    if not tags_nonempty:
        errors.append(
            _make_issue(
                code="RETRIEVAL_TAGS_EMPTY",
                field="retrieval_tags",
                message="retrieval_tags must contain at least one tag",
            )
        )

    # check 6: phase непустой
    phase_nonempty = len(metadata.phase) > 0
    checks.append(ValidationCheck(name="phase_nonempty", passed=phase_nonempty))
    if not phase_nonempty:
        errors.append(
            _make_issue(
                code="PHASE_EMPTY",
                field="phase",
                message="metadata.phase must contain at least one phase",
            )
        )

    # check 7: body_markdown не пуст
    body_nonempty = bool(card.body_markdown.strip())
    checks.append(ValidationCheck(name="body_markdown_nonempty", passed=body_nonempty))
    if not body_nonempty:
        errors.append(
            _make_issue(
                code="BODY_EMPTY",
                field="body_markdown",
                message="body_markdown must not be empty",
            )
        )

    # check 8: source_document_ids непуст (карточка должна откуда-то прийти)
    has_sources = len(card.source_document_ids) > 0
    checks.append(ValidationCheck(name="has_source_documents", passed=has_sources))
    if not has_sources:
        warnings.append(
            _make_issue(
                code="NO_SOURCE_DOCUMENTS",
                field="source_document_ids",
                message=(
                    "Card has no source_document_ids; will be hard to trace "
                    "back to the original document"
                ),
                severity=ValidationIssueSeverity.WARNING,
            )
        )

    # check 9: agent_targets — известные агенты
    unknown_agents = [a for a in metadata.agent_targets if a not in KNOWN_AGENTS]
    agents_valid = not unknown_agents
    checks.append(ValidationCheck(name="agent_targets_known", passed=agents_valid))
    if not agents_valid:
        errors.append(
            _make_issue(
                code="UNKNOWN_AGENTS",
                field="agent_targets",
                message=f"Unknown agent_targets: {unknown_agents}",
            )
        )

    # check 10: status подходящий для индексации
    # approved/chunked/embedded/indexed/published — карточка прошла validation.
    # draft/generated — не должны индексироваться.
    indexable_statuses = {
        CardStatus.METADATA_VALIDATED,
        CardStatus.APPROVED,
        CardStatus.CHUNKED,
        CardStatus.EMBEDDED,
        CardStatus.INDEXED,
        CardStatus.PUBLISHED,
    }
    if card.status in {CardStatus.DRAFT, CardStatus.GENERATED}:
        warnings.append(
            _make_issue(
                code="STATUS_NOT_INDEXABLE",
                field="status",
                message=(
                    f"Card status {card.status.value!r} is below "
                    "metadata_validated; cannot be indexed yet"
                ),
                severity=ValidationIssueSeverity.WARNING,
            )
        )
    checks.append(
        ValidationCheck(name="indexable_status", passed=card.status in indexable_statuses)
    )

    # check 11: low confidence карточки требуют review
    if metadata.confidence_level == ConfidenceLevel.LOW and card.status not in {
        CardStatus.REVIEW_REQUIRED,
        CardStatus.APPROVED,
        CardStatus.DEPRECATED,
    }:
        warnings.append(
            _make_issue(
                code="LOW_CONFIDENCE_NEEDS_REVIEW",
                field="confidence_level",
                message=(
                    "Card with confidence_level=low must be in review_required "
                    "or approved before indexing"
                ),
                severity=ValidationIssueSeverity.WARNING,
            )
        )

    # check 12: phase — instance Phase enum (защита от строкового мусора, хотя
    # Pydantic уже валидирует на создании метаданных)
    phase_types_ok = all(isinstance(p, Phase) for p in metadata.phase)
    checks.append(ValidationCheck(name="phase_types_valid", passed=phase_types_ok))

    # Финальный статус
    if errors:
        status = ValidationStatus.FAILED
        repair = _build_repair_instruction(errors)
    elif warnings:
        status = ValidationStatus.WARNING
        repair = None
    else:
        status = ValidationStatus.PASSED
        repair = None

    return ValidationReport(
        validation_report_id=f"vr_{uuid.uuid4().hex[:12]}",
        target_type=ValidationTargetType.RAG_CARD,
        target_id=card.doc_id,
        status=status,
        checks=checks,
        errors=errors,
        warnings=warnings,
        repair_instruction=repair,
        created_at=_now(),
        validator_name=VALIDATOR_NAME,
    )


def _build_repair_instruction(errors: list[ValidationIssue]) -> str:
    parts = [f"- [{e.code}] {e.message}" for e in errors]
    return "Fix the following issues before re-validating:\n" + "\n".join(parts)


def validate_metadata_only(
    metadata_dict: dict[str, object],
) -> ValidationReport:
    """Валидация только структуры RAGMetadata (используется на самом раннем этапе).

    Если сам Pydantic-парсинг падает — возвращаем report со SCHEMA_ERROR.
    """
    try:
        RAGMetadata.model_validate(metadata_dict)
    except ValidationError as exc:
        issues = [
            _make_issue(
                code="SCHEMA_ERROR",
                field=".".join(str(p) for p in err.get("loc", ())),
                message=err.get("msg", "validation error"),
            )
            for err in exc.errors()
        ]
        return ValidationReport(
            validation_report_id=f"vr_{uuid.uuid4().hex[:12]}",
            target_type=ValidationTargetType.RAG_CARD,
            target_id=str(metadata_dict.get("doc_id", "unknown")),
            status=ValidationStatus.FAILED,
            checks=[ValidationCheck(name="metadata_schema", passed=False)],
            errors=issues,
            warnings=[],
            repair_instruction=_build_repair_instruction(issues),
            created_at=_now(),
            validator_name=VALIDATOR_NAME,
        )

    return ValidationReport(
        validation_report_id=f"vr_{uuid.uuid4().hex[:12]}",
        target_type=ValidationTargetType.RAG_CARD,
        target_id=str(metadata_dict.get("doc_id", "unknown")),
        status=ValidationStatus.PASSED,
        checks=[ValidationCheck(name="metadata_schema", passed=True)],
        errors=[],
        warnings=[],
        repair_instruction=None,
        created_at=_now(),
        validator_name=VALIDATOR_NAME,
    )
