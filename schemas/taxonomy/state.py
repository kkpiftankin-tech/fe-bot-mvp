"""ClassificationState — состояние классификации одной секции.

30-битная bitmap-разметка (см. ADR-HTC-02):

    bit  29..20 — L2 (scoped under (primary_l0, primary_l1))
    bit  19..10 — L1 (scoped under primary_l0)
    bit   9.. 0 — L0 (global)

Дополнительные поля:
- primary_l0_idx, primary_l1_idx — индексы основных классов для drill-down.
- unknown_at_level ∈ {None, 0, 1, 2} — на каком уровне сработал
  cascading-unknown (см. ADR-HTC-06).
- confidence_per_level, confidence_per_bit — confidence-метрики.
- auto_created_bits — аудит, какие биты были созданы при классификации
  этой секции.

См. документы:
- docs/02-system/features/SETUP-12-llm-taxonomy-classification.md (§3, §6)
- docs/03-architecture/adr/ADR-HTC-02-bitmap-30-layout.md
- docs/03-architecture/adr/ADR-HTC-06-cascading-unknown.md
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

BITS_PER_LEVEL: int = 10
"""10 бит на уровень — стартовое ограничение, тюнится в config'е."""

LEVELS: int = 3
"""Глубина дерева классификации (L0, L1, L2)."""

BIT_MASK_L0: int = 0x000003FF  # bits 0..9
BIT_MASK_L1: int = 0x000FFC00  # bits 10..19
BIT_MASK_L2: int = 0x3FF00000  # bits 20..29
BIT_MASK_ALL: int = BIT_MASK_L0 | BIT_MASK_L1 | BIT_MASK_L2


def bit_offset(level: int, bit_in_level: int) -> int:
    """Возвращает absolute bit-position для (level, bit_in_level)."""
    if not 0 <= level <= LEVELS - 1:
        raise ValueError(f"level must be 0..{LEVELS - 1}")
    if not 0 <= bit_in_level <= BITS_PER_LEVEL - 1:
        raise ValueError(f"bit_in_level must be 0..{BITS_PER_LEVEL - 1}")
    return level * BITS_PER_LEVEL + bit_in_level


def level_mask(level: int) -> int:
    """Возвращает маску для всех бит указанного уровня."""
    if level == 0:
        return BIT_MASK_L0
    if level == 1:
        return BIT_MASK_L1
    if level == 2:
        return BIT_MASK_L2
    raise ValueError(f"level must be 0..{LEVELS - 1}")


def bits_set_at_level(bitmap: int, level: int) -> list[int]:
    """Возвращает индексы (0..9) выставленных бит в зоне уровня."""
    mask = level_mask(level)
    extracted = (bitmap & mask) >> (level * BITS_PER_LEVEL)
    return [i for i in range(BITS_PER_LEVEL) if extracted & (1 << i)]


class AutoCreationRecord(BaseModel):
    """Аудит-запись об автоматически созданном классе.

    Привязана к (taxonomy_version_id, level, parent_path, bit_index).
    Создаётся, когда auto-allocator материализует новый бит в bit-registry
    по предложению LLM (см. ADR-HTC-04).
    """

    model_config = ConfigDict(extra="forbid")

    level: int = Field(..., ge=0, le=LEVELS - 1)
    parent_path: str = Field(..., max_length=128)
    bit_index: int = Field(..., ge=0, le=BITS_PER_LEVEL - 1)
    class_slug: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    triggered_by_section_id: str = Field(..., min_length=1)
    created_at: datetime = Field(...)
    similarity_to_closest: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Cosine sim с ближайшим существующим. None если "
        "под parent_path не было существующих.",
    )
    closest_existing_slug: str | None = Field(
        default=None,
        max_length=64,
        description="Slug ближайшего существующего класса (для аудита).",
    )


class ClassificationState(BaseModel):
    """Bitmap-состояние классификации одной секции.

    Это поле выносится на ParsedSection как `classification_state` и
    становится каноническим источником для downstream:
    - DocTypeDetector читает primary_l0 → doc_type карточки.
    - PromptTemplateRegistry читает taxonomy_path для выбора шаблона.
    - RetrievalService строит фильтры на bitmap'е.
    - Analytics агрегирует по уровням / классам.

    Инварианты:
    - Если primary_l0_idx задан, то бит primary_l0_idx уровня 0
      должен быть установлен.
    - Если primary_l1_idx задан, то primary_l0_idx также задан.
    - Если unknown_at_level=k, то все биты уровней ≥ k обнулены.
    - Если primary_l0_idx is None, unknown_at_level должен быть 0
      (либо bitmap пустой и LLM не был вызван — initial state).
    """

    model_config = ConfigDict(extra="forbid")

    # --- bitmap ---
    classification_bitmap: int = Field(
        default=0,
        ge=0,
        le=BIT_MASK_ALL,
        description="30-битная маска классификации (биты 0..29).",
    )
    primary_l0_idx: int | None = Field(
        default=None,
        ge=0,
        le=BITS_PER_LEVEL - 1,
        description="Индекс primary L0-класса (argmax confidence). "
        "None если L0 не классифицирован.",
    )
    primary_l1_idx: int | None = Field(
        default=None,
        ge=0,
        le=BITS_PER_LEVEL - 1,
        description="Индекс primary L1-класса. None если L1 не "
        "классифицирован.",
    )
    unknown_at_level: int | None = Field(
        default=None,
        ge=0,
        le=LEVELS - 1,
        description="Уровень, на котором LLM ответил UNKNOWN (или confidence "
        "был ниже T_SET). None означает: либо классификация ещё не "
        "запускалась (initial), либо все 3 уровня успешно прошли.",
    )

    # --- confidence ---
    confidence_per_level: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        description="Overall confidence per level (L0, L1, L2). 0 для "
        "уровней, которые не были запрошены.",
    )
    confidence_per_bit: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence на каждый выставленный бит. Ключ — "
        "'<level>:<bit_index>' (например, '0:3').",
    )

    # --- provenance ---
    taxonomy_version_id: str = Field(
        ...,
        pattern=r"^v\d+\.\d+\.\d+$",
        description="Версия таксономии, в рамках которой выполнена "
        "классификация. Расшифровка bitmap'а возможна только в этой "
        "версии (биты могут переезжать между major-версиями).",
    )
    classification_method: str = Field(
        default="llm",
        description="llm | seeded | manual | seeded_migration. "
        "Используется для аналитики и audit'а.",
    )
    auto_created_bits: list[AutoCreationRecord] = Field(
        default_factory=list,
        description="Записи о битах, материализованных auto-allocator'ом "
        "при классификации этой секции.",
    )
    llm_trace_ids: list[str] = Field(
        default_factory=list,
        description="ID LLM-вызовов в LLMCallTraceRepository для аудита "
        "(до 3 — по одному на уровень).",
    )

    @model_validator(mode="after")
    def _bitmap_in_range(self) -> ClassificationState:
        if self.classification_bitmap & ~BIT_MASK_ALL:
            raise ValueError(
                "classification_bitmap uses bits outside the 30-bit "
                "classification zone"
            )
        return self

    @model_validator(mode="after")
    def _primary_consistency(self) -> ClassificationState:
        if self.primary_l0_idx is not None:
            mask = 1 << bit_offset(0, self.primary_l0_idx)
            if not (self.classification_bitmap & mask):
                raise ValueError(
                    "primary_l0_idx points to a bit that is not set in "
                    "classification_bitmap"
                )
        if self.primary_l1_idx is not None:
            if self.primary_l0_idx is None:
                raise ValueError(
                    "primary_l1_idx requires primary_l0_idx to be set"
                )
            mask = 1 << bit_offset(1, self.primary_l1_idx)
            if not (self.classification_bitmap & mask):
                raise ValueError(
                    "primary_l1_idx points to a bit that is not set in "
                    "classification_bitmap"
                )
        return self

    @model_validator(mode="after")
    def _cascading_unknown(self) -> ClassificationState:
        if self.unknown_at_level is None:
            return self
        # Уровни >= unknown_at_level должны быть нулевыми.
        for k in range(self.unknown_at_level, LEVELS):
            if self.classification_bitmap & level_mask(k):
                raise ValueError(
                    f"unknown_at_level={self.unknown_at_level} but bits at "
                    f"level {k} are set"
                )
        if self.unknown_at_level == 0 and self.primary_l0_idx is not None:
            raise ValueError(
                "unknown_at_level=0 forbids primary_l0_idx"
            )
        if self.unknown_at_level == 1 and self.primary_l1_idx is not None:
            raise ValueError(
                "unknown_at_level=1 forbids primary_l1_idx"
            )
        return self

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def bits_at(self, level: int) -> list[int]:
        """Возвращает индексы выставленных бит на уровне."""
        return bits_set_at_level(self.classification_bitmap, level)

    @property
    def is_classified(self) -> bool:
        """True если есть хотя бы один установленный L0-бит."""
        return bool(self.classification_bitmap & BIT_MASK_L0)

    @property
    def depth_reached(self) -> int:
        """Возвращает максимальный уровень, на котором есть выставленный бит."""
        if self.classification_bitmap & BIT_MASK_L2:
            return 2
        if self.classification_bitmap & BIT_MASK_L1:
            return 1
        if self.classification_bitmap & BIT_MASK_L0:
            return 0
        return -1
