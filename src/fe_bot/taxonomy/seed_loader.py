"""Seed-loader для taxonomy_version (SETUP-12 / T-S12-012).

Загружает YAML-файл seed/taxonomy/vX.Y.Z.yaml в Pydantic-объект
``TaxonomyVersion`` и набор ``TaxonomyBitRegistryEntry``.

Embedding'и для seed-классов вычисляются lazy (по запросу
auto-allocator'а) — здесь они None. См. ADR-HTC-04.

Формат YAML:
    version_id: v1.0.0
    created_at: "2026-06-26T00:00:00Z"
    description: |
      ...
    entries:
      - level: 0
        parent_path: ""
        bit_index: 0
        class_slug: task
        display_name_ru: "Задача"
        display_name_en: "Task"
        description: |
          ...
        doc_type_hint: task_card

При отсутствии optional полей (display_name_en, doc_type_hint) —
defaults из Pydantic-схемы.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)


class SeedFormatError(ValueError):
    """Поднимается, когда seed-YAML не соответствует ожидаемому формату."""


def load_seed_taxonomy(path: str | Path) -> TaxonomyVersion:
    """Парсит seed-YAML и возвращает TaxonomyVersion(is_active=True).

    Все entries разделяют version_id с верхним уровнем; created_at
    наследуется из верхнего уровня, если не задан per-entry.

    Raises:
        FileNotFoundError: путь не существует.
        SeedFormatError: YAML некорректный либо отсутствуют обязательные
            поля.
        ValidationError: данные не проходят Pydantic-схему.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Seed taxonomy file not found: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SeedFormatError(
            f"Seed YAML must be a mapping at top level, got {type(raw).__name__}"
        )
    version_id = raw.get("version_id")
    if not isinstance(version_id, str):
        raise SeedFormatError("Missing or invalid 'version_id' in seed YAML")
    created_at_raw = raw.get("created_at")
    created_at = _parse_datetime(created_at_raw, field="created_at")
    description = raw.get("description") or ""
    entries_raw = raw.get("entries") or []
    if not isinstance(entries_raw, list):
        raise SeedFormatError("'entries' must be a list in seed YAML")
    entries: list[TaxonomyBitRegistryEntry] = []
    for idx, entry_data in enumerate(entries_raw):
        if not isinstance(entry_data, dict):
            raise SeedFormatError(
                f"entries[{idx}] must be a mapping, got {type(entry_data).__name__}"
            )
        try:
            entries.append(
                _build_entry(entry_data, version_id=version_id, created_at=created_at)
            )
        except ValidationError as exc:
            raise SeedFormatError(
                f"entries[{idx}] validation failed: {exc.errors()[:3]}"
            ) from exc
    try:
        return TaxonomyVersion(
            version_id=version_id,
            created_at=created_at,
            description=description,
            is_active=True,
            entries=entries,
        )
    except ValidationError as exc:
        raise SeedFormatError(
            f"TaxonomyVersion validation failed: {exc.errors()[:3]}"
        ) from exc


def _build_entry(
    data: dict[str, Any],
    *,
    version_id: str,
    created_at: datetime,
) -> TaxonomyBitRegistryEntry:
    payload: dict[str, Any] = {
        "version_id": version_id,
        "created_at": created_at,
        "auto_created": False,
        "level": data.get("level"),
        "parent_path": data.get("parent_path", ""),
        "bit_index": data.get("bit_index"),
        "class_slug": data.get("class_slug"),
        "display_name_ru": data.get("display_name_ru"),
        "display_name_en": data.get("display_name_en", ""),
        "description": (data.get("description") or "").strip(),
        "doc_type_hint": data.get("doc_type_hint"),
    }
    return TaxonomyBitRegistryEntry(**payload)


def _parse_datetime(value: Any, *, field: str) -> datetime:
    if value is None:
        raise SeedFormatError(f"Missing required '{field}' field")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        from datetime import UTC

        # Допускаем формат ISO с возможным 'Z' в конце.
        text = value.replace("Z", "+00:00") if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise SeedFormatError(
                f"Invalid ISO datetime in '{field}': {value!r}"
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    raise SeedFormatError(
        f"'{field}' must be ISO datetime string, got {type(value).__name__}"
    )
