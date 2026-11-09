"""Unit-тесты seed_loader (SETUP-12 / T-S12-012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fe_bot.taxonomy.seed_loader import SeedFormatError, load_seed_taxonomy

pytestmark = pytest.mark.unit


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "seed.yaml"
    p.write_text(content, encoding="utf-8")
    return p


class TestLoadValidSeed:
    def test_load_minimal(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
version_id: v1.0.0
created_at: "2026-06-26T00:00:00Z"
description: minimal
entries:
  - level: 0
    parent_path: ""
    bit_index: 0
    class_slug: task
    display_name_ru: "Задача"
    description: |
      Описание задачи для теста.
    doc_type_hint: task_card
""",
        )
        version = load_seed_taxonomy(path)
        assert version.version_id == "v1.0.0"
        assert version.is_active is True
        assert len(version.entries) == 1
        e = version.entries[0]
        assert e.class_slug == "task"
        assert e.doc_type_hint == "task_card"
        assert e.auto_created is False

    def test_load_actual_v1_0_0(self) -> None:
        """Integration: загрузка реального seed/taxonomy/v1_0_0.yaml."""
        repo_root = Path(__file__).resolve().parents[3]
        seed_path = repo_root / "seed" / "taxonomy" / "v1_0_0.yaml"
        version = load_seed_taxonomy(seed_path)
        assert version.version_id == "v1.0.0"
        assert version.is_active is True
        # 9 L0 классов (bit 9 свободен) — см. seed
        assert len(version.entries) == 9
        slugs = {e.class_slug for e in version.entries}
        expected = {
            "task",
            "schema",
            "analytics",
            "glossary",
            "validation_rule",
            "question_template",
            "domain_profile",
            "process",
            "reference",
        }
        assert slugs == expected

    def test_empty_entries(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
version_id: v1.0.0
created_at: "2026-06-26T00:00:00Z"
entries: []
""",
        )
        version = load_seed_taxonomy(path)
        assert version.entries == []


class TestInvalidSeed:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_seed_taxonomy(tmp_path / "missing.yaml")

    def test_non_mapping_top_level(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "- 1\n- 2\n")
        with pytest.raises(SeedFormatError, match="mapping at top level"):
            load_seed_taxonomy(path)

    def test_missing_version_id(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
created_at: "2026-06-26T00:00:00Z"
entries: []
""",
        )
        with pytest.raises(SeedFormatError, match="version_id"):
            load_seed_taxonomy(path)

    def test_missing_created_at(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
version_id: v1.0.0
entries: []
""",
        )
        with pytest.raises(SeedFormatError, match="created_at"):
            load_seed_taxonomy(path)

    def test_invalid_datetime(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
version_id: v1.0.0
created_at: "not-a-date"
entries: []
""",
        )
        with pytest.raises(SeedFormatError, match="ISO datetime"):
            load_seed_taxonomy(path)

    def test_invalid_entry_validation(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
version_id: v1.0.0
created_at: "2026-06-26T00:00:00Z"
entries:
  - level: 0
    parent_path: ""
    bit_index: 99
    class_slug: task
    display_name_ru: "Задача"
    description: "Описание класса"
""",
        )
        with pytest.raises(SeedFormatError, match="validation failed"):
            load_seed_taxonomy(path)

    def test_entries_must_be_list(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
version_id: v1.0.0
created_at: "2026-06-26T00:00:00Z"
entries: "not a list"
""",
        )
        with pytest.raises(SeedFormatError, match="must be a list"):
            load_seed_taxonomy(path)
