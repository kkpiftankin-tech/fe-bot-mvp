"""ParsedSectionDTO (DTO-10) — смысловая секция исходного документа.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-10.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SectionType(StrEnum):
    TASK = "task"
    SCHEMA = "schema"
    ANALYTICS = "analytics"
    GLOSSARY = "glossary"
    VALIDATION = "validation"
    DOMAIN_PROFILE = "domain_profile"
    OTHER = "other"


class ParsedSection(BaseModel):
    """Извлечённая секция документа."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = Field(..., min_length=1)
    source_document_id: str = Field(..., min_length=1)
    setup_job_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=512)
    section_path: list[str] = Field(default_factory=list)
    section_type: SectionType = SectionType.OTHER
    raw_text: str = Field(..., min_length=1)
    normalized_text: str = Field(..., min_length=1)
    start_offset: int | None = Field(None, ge=0)
    end_offset: int | None = Field(None, ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _offsets_consistent(self) -> ParsedSection:
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("end_offset must be >= start_offset")
        return self
