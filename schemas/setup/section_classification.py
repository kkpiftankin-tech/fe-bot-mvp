"""SectionClassification DTO (SETUP-04) — запись о классификации секции.

Фиксирует решение rule-based (или будущего LLM-fallback) классификатора
для конкретной ParsedSection. Неизменяема после создания.

Source of truth — SETUP-04 spec §15.3.
Storage — PostgreSQL, таблица section_classifications. MVP: in-memory.
Producer — SVC-07 Document Parser Service (rule-based classifier).
Consumers — SVC-09 RAG Card Generator, SVC-08 Metadata Validation Service,
            SVC-36 Audit Service.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClassificationMethod(StrEnum):
    """Метод, которым была проведена классификация секции.

    rule_based — детерминированные правила (MVP, основной путь).
    llm_fallback — LLM-классификация для неопределённых случаев (post-MVP).
    manual — ручная правка пользователем через UI.
    """

    RULE_BASED = "rule_based"
    LLM_FALLBACK = "llm_fallback"
    MANUAL = "manual"


class SectionClassification(BaseModel):
    """Запись о классификации секции.

    Каждая ParsedSection может иметь несколько записей классификации:
    первичную (rule_based) и, опционально, ревизии (manual, llm_fallback).
    Конкурирующие записи упорядочиваются по created_at.

    Frozen=True: запись неизменяема после создания.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    classification_id: str = Field(..., min_length=1, description="UUID записи классификации.")
    section_id: str = Field(..., min_length=1, description="FK → parsed_sections.section_id.")
    candidate_type: str = Field(
        ..., min_length=1, description="Предлагаемый SectionType (строковое значение enum)."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Уверенность классификатора в [0.0, 1.0]."
    )
    method: ClassificationMethod = Field(..., description="Метод классификации.")
    model_name: str | None = Field(
        None,
        max_length=128,
        description="Имя LLM-модели при method=llm_fallback. None для rule_based и manual.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Краткое обоснование решения (правило или промпт-вывод).",
    )
    created_at: datetime = Field(..., description="Время создания записи (UTC).")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные данные: matched_keywords, rule_id и др.",
    )
