"""CardValidationPrecheck (SETUP-05 / T-S05-018).

Blocking + warning проверки структуры RAGCardDraft до сохранения в Card Registry.
Отделён от full metadata validation (SETUP-07): здесь — только то, без чего
карточку нельзя считать ``generated``.

Coded outputs:
- Blocking errors (passed=False):
    DOC_ID_MISSING, DOC_TYPE_INVALID, SOURCE_FILES_EMPTY, SOURCE_SECTIONS_EMPTY,
    CARD_BODY_EMPTY, FRONT_MATTER_INVALID.
- Warnings (passed=True, но review_required eligible):
    RETRIEVAL_TAGS_EMPTY, MISSING_OPTIONAL_METADATA.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from schemas.setup.rag_card_generation_report import CardValidationReportDTO

# 7 MVP doc_types из docs/06-rag/metadata-schema.md §1.
_MVP_DOC_TYPES = frozenset(
    {
        "schema_card",
        "task_card",
        "analytics_card",
        "field_definition_card",
        "feature_pattern_card",
        "validation_rule_card",
        "question_template_card",
    }
)

_BODY_MIN_LEN = 20


class RAGCardDraft(BaseModel):
    """Переходная Pydantic-модель для LLM output (до сохранения как RAGCard).

    LLM возвращает JSON, который валидируется по этой schema внутри
    ``LLMGateway.generate_structured``. После прохождения precheck draft
    превращается в финальный ``RAGCard`` + ``RAGCardMetadataDTO``.
    """

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(..., min_length=1)
    doc_type: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=512)
    body_markdown: str = Field(..., min_length=1)
    front_matter: dict[str, Any] = Field(default_factory=dict)
    source_files: list[str] = Field(default_factory=list)
    source_sections: list[str] = Field(default_factory=list)
    retrieval_tags: list[str] = Field(default_factory=list)
    # LLM может вернуть confidence как hint (0..1). Calculator потом override.
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    # Дополнительные warnings, которые LLM может сообщить через extra field.
    warnings: list[str] = Field(default_factory=list)


def _err(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **extra}


class CardValidationPrecheck:
    """Stateless precheck. Не модифицирует draft, возвращает CardValidationReportDTO."""

    def check(
        self,
        draft: RAGCardDraft,
        *,
        card_version: str = "1.0",
    ) -> CardValidationReportDTO:
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        # Blocking.
        if not draft.doc_id.strip():
            errors.append(_err("DOC_ID_MISSING", "doc_id is empty"))
        if draft.doc_type not in _MVP_DOC_TYPES:
            errors.append(
                _err(
                    "DOC_TYPE_INVALID",
                    f"doc_type {draft.doc_type!r} is not in MVP enum",
                    doc_type=draft.doc_type,
                )
            )
        if not draft.source_files:
            errors.append(_err("SOURCE_FILES_EMPTY", "source_files is empty"))
        if not draft.source_sections:
            errors.append(_err("SOURCE_SECTIONS_EMPTY", "source_sections is empty"))
        body_stripped = (draft.body_markdown or "").strip()
        if len(body_stripped) < _BODY_MIN_LEN:
            errors.append(
                _err(
                    "CARD_BODY_EMPTY",
                    f"body_markdown shorter than {_BODY_MIN_LEN} chars",
                    actual_len=len(body_stripped),
                )
            )
        if not self._front_matter_valid(draft):
            errors.append(
                _err(
                    "FRONT_MATTER_INVALID",
                    "front_matter missing required keys (doc_id, doc_type)",
                )
            )

        # Warnings.
        if not draft.retrieval_tags:
            warnings.append(_err("RETRIEVAL_TAGS_EMPTY", "retrieval_tags is empty"))
        if not draft.front_matter.get("domain") or not draft.front_matter.get("phase"):
            warnings.append(
                _err(
                    "MISSING_OPTIONAL_METADATA",
                    "domain or phase missing in front_matter",
                )
            )

        return CardValidationReportDTO(
            validation_report_id=f"val_{uuid.uuid4().hex[:12]}",
            doc_id=draft.doc_id or "unknown",
            card_version=card_version,
            passed=not errors,
            errors=errors,
            warnings=warnings,
            checked_at=datetime.now(tz=UTC),
        )

    @staticmethod
    def _front_matter_valid(draft: RAGCardDraft) -> bool:
        fm = draft.front_matter
        if not isinstance(fm, dict):
            return False
        # Минимальные required ключи (см. docs/06-rag/metadata-schema.md §3).
        return bool(fm.get("doc_id")) and bool(fm.get("doc_type"))
