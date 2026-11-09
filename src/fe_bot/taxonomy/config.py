"""Taxonomy config loader (SETUP-12 / T-S12-020).

Парсит ``config/taxonomy/auto_allocation.yaml`` в Pydantic-настройки.
Все пороги hot-tunable — поддерживается reload без перезапуска
сервиса через ``AutoAllocatorConfig.from_yaml(path)``.

Структура YAML — см. config/taxonomy/auto_allocation.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class TaxonomyConfigError(ValueError):
    """Конфиг не парсится / не валиден."""


class AutoAllocatorConfig(BaseModel):
    """Параметры авто-классификации и allocation'а.

    Значения дублируют дефолты из YAML; конструктор без аргументов
    возвращает стартовые рекомендации MVP. ``from_yaml`` грузит и
    перезаписывает.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Capacity
    max_depth: int = Field(default=3, ge=1, le=10)
    classes_per_level: int = Field(default=10, ge=2, le=64)

    # Confidence thresholds
    t_set: float = Field(default=0.60, ge=0.0, le=1.0)
    min_new_class_conf: float = Field(default=0.65, ge=0.0, le=1.0)

    # Similarity gates
    sim_reuse: float = Field(default=0.85, ge=0.0, le=1.0)
    sim_force_merge: float = Field(default=0.70, ge=0.0, le=1.0)

    # Multi-class behaviour
    multi_class_delta_threshold: float = Field(default=0.15, ge=0.0, le=1.0)

    # Overflow strategy (только force_merge_to_closest_with_warning в MVP)
    overflow_strategy: str = Field(
        default="force_merge_to_closest_with_warning"
    )

    # Embedding
    embedding_model: str = Field(default="nomic-embed-text")
    embedding_dim: int = Field(default=384, ge=1, le=8192)

    # LLM
    llm_model: str = Field(default="llama3.2")
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_attempts_per_level: int = Field(default=3, ge=1, le=10)
    llm_timeout_sec: int = Field(default=60, ge=1, le=600)

    # Versioning
    initial_version_id: str = Field(default="v1.0.0")
    auto_bump_policy: str = Field(default="patch_on_first_create")

    @classmethod
    def from_yaml(cls, path: str | Path) -> AutoAllocatorConfig:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Taxonomy config not found: {p}")
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise TaxonomyConfigError(f"Invalid YAML in {p}: {exc}") from exc
        if not isinstance(raw, dict):
            raise TaxonomyConfigError(
                f"Config YAML must be a mapping, got {type(raw).__name__}"
            )
        flat = _flatten_thresholds(raw)
        try:
            return cls(**flat)
        except ValidationError as exc:
            raise TaxonomyConfigError(
                f"Config validation failed: {exc.errors()[:3]}"
            ) from exc


def _flatten_thresholds(raw: dict[str, Any]) -> dict[str, Any]:
    """YAML кладёт пороги в раздел ``thresholds:``; в Pydantic — плоские
    поля. Совмещаем плоские ключи верхнего уровня + вложенный
    ``thresholds`` блок.
    """
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key == "thresholds" and isinstance(value, dict):
            # Внутренние ключи YAML — UPPERCASE; приводим к snake_case.
            for tkey, tval in value.items():
                out[tkey.lower()] = tval
            continue
        out[key.lower()] = value
    return out


def default_config_path() -> Path:
    """Возвращает путь к config'у в стандартной layout-папке проекта."""
    return (
        Path(__file__).resolve().parents[3]
        / "config"
        / "taxonomy"
        / "auto_allocation.yaml"
    )
