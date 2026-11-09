"""Taxonomy Bit Registry — реестр (version_id, level, parent_path, bit_index)
→ class metadata.

Канонический источник истины для расшифровки bitmap'а классификации.

См. документы:
- docs/02-system/features/SETUP-12-llm-taxonomy-classification.md (§4)
- docs/03-architecture/adr/ADR-HTC-02-bitmap-30-layout.md
- docs/03-architecture/adr/ADR-HTC-04-automatic-allocation.md
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_LEVEL: int = 2
MAX_BITS_PER_LEVEL: int = 10
"""Максимум классов на каждом уровне (L0/L1/L2). Тюнится в config'е."""


class TaxonomyBitStatus(StrEnum):
    """Состояние класса (бита) в реестре."""

    ACTIVE = "active"
    DEPRECATED_MERGED = "deprecated_merged"


class TaxonomyBitRegistryEntry(BaseModel):
    """Один слот в bit-registry: класс уровня k под parent_path.

    Identity: (version_id, level, parent_path, bit_index).
    Бит-позиция в bitmap'е = level * 10 + bit_index (см. ADR-HTC-02).
    """

    model_config = ConfigDict(extra="forbid")

    # --- identity ---
    version_id: str = Field(
        ...,
        min_length=1,
        max_length=32,
        pattern=r"^v\d+\.\d+\.\d+$",
        description="Semver taxonomy_version (например, v1.0.0).",
    )
    level: int = Field(
        ...,
        ge=0,
        le=MAX_LEVEL,
        description="Уровень классификации: 0 (root), 1, 2.",
    )
    parent_path: str = Field(
        ...,
        max_length=128,
        description="Слаговый путь предков, разделитель '.'. "
        "Для level=0 — пустая строка. "
        "Для level=1 — slug L0-класса. "
        "Для level=2 — '<l0_slug>.<l1_slug>'.",
    )
    bit_index: int = Field(
        ...,
        ge=0,
        le=MAX_BITS_PER_LEVEL - 1,
        description="Индекс бита в зоне уровня (0..9).",
    )

    # --- class metadata ---
    class_slug: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="Stable kebab-case-английский идентификатор класса.",
    )
    display_name_ru: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Отображаемое имя класса (русский).",
    )
    display_name_en: str = Field(
        default="",
        max_length=128,
        description="Отображаемое имя класса (английский, optional).",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Описание класса. Используется в prompt'е и для "
        "embedding'а (similarity-gate).",
    )

    # --- lifecycle ---
    status: TaxonomyBitStatus = Field(
        default=TaxonomyBitStatus.ACTIVE,
        description="active | deprecated_merged.",
    )
    merged_into_slug: str | None = Field(
        default=None,
        max_length=64,
        description="Если status=deprecated_merged — slug целевого "
        "класса, в который смержен.",
    )

    # --- provenance ---
    auto_created: bool = Field(
        default=False,
        description="True если бит создан auto-allocator'ом (через LLM-"
        "proposal). False для seed-классов.",
    )
    created_at: datetime = Field(..., description="Время создания (UTC).")
    created_by_section: str | None = Field(
        default=None,
        description="section_id, чьё LLM-предложение триггернуло "
        "создание. None для seed.",
    )

    # --- usage stats ---
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Сколько раз бит был выставлен (для drift-анализа).",
    )

    # --- downstream metadata ---
    doc_type_hint: str | None = Field(
        default=None,
        max_length=64,
        description="Подсказка для RAG-card DocTypeDetector (например, "
        "'schema_card' для L0='schema'). Если None — fallback вверх "
        "по path.",
    )

    # --- similarity routing ---
    embedding: list[float] | None = Field(
        default=None,
        description="Embedding-вектор от (display_name_ru + description). "
        "Используется similarity-gate. None для seed (вычисляется при "
        "загрузке).",
    )

    @model_validator(mode="after")
    def _parent_path_consistency(self) -> TaxonomyBitRegistryEntry:
        if self.level == 0 and self.parent_path != "":
            raise ValueError("Level 0 entries must have empty parent_path")
        if self.level >= 1 and not self.parent_path:
            raise ValueError(
                f"Level {self.level} entries require non-empty parent_path"
            )
        if self.level == 1 and "." in self.parent_path:
            raise ValueError(
                "Level 1 parent_path must be single slug (no '.')"
            )
        if self.level == 2 and self.parent_path.count(".") != 1:
            raise ValueError(
                "Level 2 parent_path must be '<l0_slug>.<l1_slug>'"
            )
        return self

    @model_validator(mode="after")
    def _merged_invariant(self) -> TaxonomyBitRegistryEntry:
        if self.status == TaxonomyBitStatus.DEPRECATED_MERGED:
            if not self.merged_into_slug:
                raise ValueError(
                    "deprecated_merged status requires merged_into_slug"
                )
        elif self.merged_into_slug is not None:
            raise ValueError(
                "merged_into_slug only valid with deprecated_merged status"
            )
        return self


class TaxonomyVersion(BaseModel):
    """Snapshot реестра под конкретной версией.

    Версионирование: semver. Bump:
    - patch — auto-allocated новый класс (runtime, без рестарта).
    - minor — добавлен seed-класс через миграцию.
    - major — реструктуризация (например, переезд parent_path'ов).

    См. ADR-HTC-05.
    """

    model_config = ConfigDict(extra="forbid")

    version_id: str = Field(
        ...,
        pattern=r"^v\d+\.\d+\.\d+$",
        description="Semver идентификатор версии.",
    )
    created_at: datetime = Field(...)
    description: str = Field(default="", max_length=1024)
    is_active: bool = Field(
        default=True,
        description="True для текущей рабочей версии. Только одна "
        "версия одновременно может быть active.",
    )
    entries: list[TaxonomyBitRegistryEntry] = Field(
        default_factory=list,
        description="Все слоты этой версии (любого уровня).",
    )

    @model_validator(mode="after")
    def _entries_belong_to_version(self) -> TaxonomyVersion:
        for entry in self.entries:
            if entry.version_id != self.version_id:
                raise ValueError(
                    f"Entry {entry.class_slug} has version_id "
                    f"{entry.version_id}, expected {self.version_id}"
                )
        return self

    @model_validator(mode="after")
    def _unique_identity(self) -> TaxonomyVersion:
        seen_positions = set()
        seen_slugs_per_parent = set()
        for entry in self.entries:
            pos_key = (entry.level, entry.parent_path, entry.bit_index)
            if pos_key in seen_positions:
                raise ValueError(
                    f"Duplicate bit position {pos_key} in version "
                    f"{self.version_id}"
                )
            seen_positions.add(pos_key)
            slug_key = (entry.level, entry.parent_path, entry.class_slug)
            if slug_key in seen_slugs_per_parent:
                raise ValueError(
                    f"Duplicate class_slug {entry.class_slug} under "
                    f"({entry.level}, '{entry.parent_path}') in version "
                    f"{self.version_id}"
                )
            seen_slugs_per_parent.add(slug_key)
        return self
