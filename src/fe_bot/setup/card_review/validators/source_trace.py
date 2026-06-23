"""CardSourceTraceValidator (SETUP-06 / T-S06-012).

Проверяет, что у RAG-карточки есть валидный source trace (source_document_id +
source_section_id). Approve без source trace запрещён (AC-16).

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §11.1.
"""

from __future__ import annotations

from typing import Protocol

from schemas.rag.rag_card import RAGCard

from .body import ValidationError, ValidationResult


class _SourceRegistryLike(Protocol):
    def exists(self, source_document_id: str) -> bool: ...


class _ParsedSectionRepoLike(Protocol):
    def exists(self, section_id: str) -> bool: ...


class CardSourceTraceValidator:
    """Проверяет source trace карточки.

    Errors:
    - ``SOURCE_TRACE_REQUIRED`` — у карточки нет source_section_ids или
      source_document_ids.
    - ``SOURCE_DOCUMENT_NOT_FOUND`` — заявленный source_document_id отсутствует.
    - ``SOURCE_SECTION_NOT_FOUND`` — заявленный source_section_id отсутствует.
    """

    def __init__(
        self,
        *,
        source_registry: _SourceRegistryLike | None = None,
        parsed_section_repo: _ParsedSectionRepoLike | None = None,
    ) -> None:
        self._source_registry = source_registry
        self._parsed_sections = parsed_section_repo

    def validate(self, card: RAGCard) -> ValidationResult:
        errors: list[ValidationError] = []

        # Минимальное требование: должен быть хотя бы один source_section_id
        # или source_document_id (см. AC-16).
        has_sections = bool(card.source_section_ids)
        has_documents = bool(card.source_document_ids)
        if not has_sections and not has_documents:
            errors.append(
                ValidationError(
                    code="SOURCE_TRACE_REQUIRED",
                    message="У карточки отсутствует source trace",
                )
            )
            return ValidationResult(passed=False, errors=errors)

        # Если есть registry — проверяем существование документов и секций.
        if self._source_registry is not None:
            for doc_id in card.source_document_ids:
                if not self._source_registry.exists(doc_id):
                    errors.append(
                        ValidationError(
                            code="SOURCE_DOCUMENT_NOT_FOUND",
                            message=f"Source document {doc_id!r} не найден",
                        )
                    )

        if self._parsed_sections is not None:
            for section_id in card.source_section_ids:
                if not self._parsed_sections.exists(section_id):
                    errors.append(
                        ValidationError(
                            code="SOURCE_SECTION_NOT_FOUND",
                            message=f"Source section {section_id!r} не найдена",
                        )
                    )

        return ValidationResult(passed=not errors, errors=errors)
