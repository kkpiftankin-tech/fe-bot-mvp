"""CardBodyValidator (SETUP-06 / T-S06-013).

Проверяет Markdown body карточки перед approve. Errors:
- ``CARD_BODY_EMPTY`` — body is None или whitespace-only.
- ``CARD_BODY_TOO_SHORT`` — body короче ``MIN_BODY_LENGTH``.
- ``CARD_BODY_DANGEROUS_HTML`` — обнаружены опасные HTML/JS теги.

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §11.1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from schemas.rag.rag_card import RAGCard

MIN_BODY_LENGTH = 20

# Опасные теги/паттерны (case-insensitive). XSS защита для preview.
_DANGEROUS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"<iframe\b", re.IGNORECASE),
    re.compile(r"<object\b", re.IGNORECASE),
    re.compile(r"<embed\b", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on(click|error|load|mouseover)\s*=", re.IGNORECASE),
)


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


class CardBodyValidator:
    """Валидатор Markdown body."""

    def validate(self, card: RAGCard) -> ValidationResult:
        errors: list[ValidationError] = []
        body = card.body_markdown or ""
        stripped = body.strip()

        if not stripped:
            errors.append(
                ValidationError(
                    code="CARD_BODY_EMPTY",
                    message="Body карточки пустой",
                )
            )
            return ValidationResult(passed=False, errors=errors)

        if len(stripped) < MIN_BODY_LENGTH:
            errors.append(
                ValidationError(
                    code="CARD_BODY_TOO_SHORT",
                    message=f"Body карточки короче {MIN_BODY_LENGTH} символов",
                )
            )

        for pattern in _DANGEROUS_PATTERNS:
            if pattern.search(body):
                errors.append(
                    ValidationError(
                        code="CARD_BODY_DANGEROUS_HTML",
                        message=f"Body содержит небезопасный паттерн: {pattern.pattern}",
                    )
                )
                break

        return ValidationResult(passed=not errors, errors=errors)
