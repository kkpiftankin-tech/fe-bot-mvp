"""ParsedSectionDTO (DTO-10) — смысловая секция исходного документа.

Расширено в SETUP-04:
- SectionType: добавлены VALIDATION_RULE, QUESTION_TEMPLATE, UNKNOWN;
  переименован OTHER → UNKNOWN (OTHER оставлен как alias для обратной
  совместимости — значение строки совпадает, поэтому десериализация не ломается).
- ParsedSectionStatus: новый enum статуса секции в рамках ParseJob.
- Новые обязательные поля: parse_job_id (был setup_job_id), section_index,
  parent_section_id, heading_path, section_status, content_hash,
  classification_method, structural_payload.
- section_path переименован в heading_path (section_path оставлен как
  deprecated alias через Field(alias=...)) — см. backward-compat ниже.

BACKWARD-COMPAT NOTE (SETUP-01/02/03):
  Код, создающий ParsedSection со старыми полями section_path / setup_job_id,
  должен быть обновлён до нового API. Временный слой совместимости:
  модель принимает section_path через model_validator и копирует в heading_path.

Source of truth — docs/03-architecture/services/data-transfer-objects.md#dto-10.
Storage — PostgreSQL, таблица parsed_sections. MVP: in-memory в ParseService.
Producer — SVC-07 Document Parser Service.
Consumers — SVC-09 RAG Card Generator, SVC-08 Metadata Validation Service,
            SVC-06 Source Registry, SVC-35 Analytics Service, SVC-36 Audit Service.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from schemas.classifier.classification_result import FragmentClassificationResult
from schemas.taxonomy.state import ClassificationState

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SectionType(StrEnum):
    """Семантический тип секции документа.

    SETUP-01/02/03 использовали: TASK, SCHEMA, ANALYTICS, GLOSSARY,
    VALIDATION, DOMAIN_PROFILE, OTHER.

    SETUP-04 расширяет до:
    - VALIDATION_RULE  — отдельное правило валидации данных.
    - QUESTION_TEMPLATE — шаблон вопроса для RAG-retrieval smoke tests.
    - UNKNOWN — не удалось классифицировать (заменяет OTHER).

    Для обратной совместимости: OTHER и DOMAIN_PROFILE сохранены.
    Новый код должен использовать UNKNOWN вместо OTHER.
    """

    TASK = "task"
    SCHEMA = "schema"
    ANALYTICS = "analytics"
    GLOSSARY = "glossary"
    # SETUP-01/02/03 legacy
    VALIDATION = "validation"
    DOMAIN_PROFILE = "domain_profile"
    OTHER = "other"  # deprecated, используй UNKNOWN
    # SETUP-04 additions
    VALIDATION_RULE = "validation_rule"
    QUESTION_TEMPLATE = "question_template"
    UNKNOWN = "unknown"


class ParsedSectionStatus(StrEnum):
    """Статус секции в рамках pipeline обработки.

    Определяет, на каком этапе находится секция и можно ли её
    передавать downstream (RAG card generator, индексация).
    """

    EXTRACTED = "extracted"  # только что извлечена
    CLASSIFIED = "classified"  # тип определён с высокой уверенностью
    LOW_CONFIDENCE = "low_confidence"  # уверенность классификации ниже порога
    IGNORED = "ignored"  # исключена из pipeline (пустая, мусор)
    INVALID = "invalid"  # не прошла структурную валидацию
    READY_FOR_RAG_CARD_GENERATION = "ready_for_rag_card_generation"  # готова к downstream
    STALE = "stale"  # документ обновлён, секция устарела


# ---------------------------------------------------------------------------
# ParsedSection model
# ---------------------------------------------------------------------------


class ParsedSection(BaseModel):
    """Извлечённая секция документа (DTO-10, SETUP-04-расширение).

    validate_assignment=False: модель содержит cross-field invariants
    (offsets, content_hash), для которых validate_assignment=True создаёт
    проблемы при частичном обновлении полей.
    """

    # populate_by_name=True позволяет конструктору принимать как
    # parse_job_id (новое имя), так и setup_job_id (старое — SETUP-01/02/03).
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # --- identity ---
    section_id: str = Field(..., min_length=1, description="UUID секции.")
    parse_job_id: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("parse_job_id", "setup_job_id"),
        description=(
            "FK → parse_jobs.parse_job_id. SETUP-04: replaces setup_job_id. "
            "Старое имя setup_job_id принимается как alias для backward-compat."
        ),
    )
    source_document_id: str = Field(..., min_length=1, description="FK → source_documents.")
    section_index: int = Field(
        default=0,
        ge=0,
        description="Порядковый номер секции в документе (0-based). "
        "Default=0 для backward-compat с SETUP-01/02/03.",
    )
    parent_section_id: str | None = Field(
        None,
        description="section_id родительской секции для иерархических документов.",
    )

    # --- classification ---
    heading_path: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("heading_path", "section_path"),
        description=(
            "Путь заголовков от корня до данной секции: ['Chapter 1', 'Section 1.2']. "
            "Старое имя section_path принимается как alias."
        ),
    )
    title: str = Field(..., min_length=1, max_length=512, description="Заголовок секции.")
    # Default OTHER (SETUP-01..03 backward-compat). Новый код должен явно
    # передавать UNKNOWN; downstream обрабатывает оба значения одинаково.
    section_type: SectionType = SectionType.OTHER
    section_status: ParsedSectionStatus = ParsedSectionStatus.EXTRACTED
    classification_method: str = Field(
        "rule_based",
        description="Метод классификации (ClassificationMethod.value). "
        "Строка для избегания циклического импорта.",
    )

    # --- content ---
    raw_text: str = Field(..., min_length=1, description="Исходный текст без нормализации.")
    normalized_text: str = Field(
        ...,
        min_length=1,
        description="Нормализованный текст: collapsed whitespace, strip, lower-case где применимо.",
    )
    start_offset: int | None = Field(
        None, ge=0, description="Байтовый/символьный offset начала в файле."
    )
    end_offset: int | None = Field(
        None, ge=0, description="Байтовый/символьный offset конца в файле."
    )
    content_hash: str = Field(
        default="",
        description=(
            "SHA-256 hex (64 символа) от normalized_text. Используется для дедупликации. "
            "Если не передан — вычисляется автоматически в model_validator."
        ),
    )

    # --- quality ---
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность классификации.")

    # --- structured payload ---
    structural_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Структурированные вложения: tables (list[dict]), "
        "json_blocks (list[dict]), links (list[str]).",
    )

    # --- SETUP-12: hierarchical taxonomy (legacy, см. classifier_result ниже) ---
    classification_state: ClassificationState | None = Field(
        default=None,
        description=(
            "SETUP-12 (legacy, заменено SETUP-13 — см. ADR-HTC-09): "
            "иерархическое bitmap-состояние классификации. Больше не "
            "заполняется новым кодом — оставлено для обратной "
            "совместимости с ранее сохранёнными секциями."
        ),
    )

    # --- SETUP-13: classifier tree (ADR-HTC-09) ---
    classifier_result: FragmentClassificationResult | None = Field(
        default=None,
        description=(
            "SETUP-13: результат многоуровневой классификации по дереву "
            "классификаторов (путь узлов от корня + confidence/reason на "
            "каждом уровне). None означает, что классификация по дереву "
            "не запускалась (FE_BOT_TAXONOMY_MODE != 'llm')."
        ),
    )

    # --- timestamps & metadata ---
    created_at: datetime = Field(..., description="Время создания записи (UTC).")
    metadata: dict[str, Any] = Field(default_factory=dict)

    # ---------------------------------------------------------------------------
    # Validators
    # ---------------------------------------------------------------------------

    @model_validator(mode="after")
    def _offsets_consistent(self) -> ParsedSection:
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("end_offset must be >= start_offset")
        return self

    @model_validator(mode="after")
    def _content_hash_format(self) -> ParsedSection:
        # Auto-derive content_hash из normalized_text если не задан.
        if not self.content_hash:
            object.__setattr__(
                self,
                "content_hash",
                hashlib.sha256(self.normalized_text.encode("utf-8")).hexdigest(),
            )
        elif not _SHA256_RE.match(self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 hex string (64 chars)")
        return self

    # ---------------------------------------------------------------------------
    # Backward-compat read properties (SETUP-01/02/03)
    # ---------------------------------------------------------------------------

    @property
    def section_path(self) -> list[str]:
        """Deprecated alias: используй heading_path. Оставлено для совместимости
        с SETUP-01/02/03 кодом и тестами, читающими старое имя."""
        return self.heading_path

    @property
    def setup_job_id(self) -> str:
        """Deprecated alias: используй parse_job_id."""
        return self.parse_job_id
