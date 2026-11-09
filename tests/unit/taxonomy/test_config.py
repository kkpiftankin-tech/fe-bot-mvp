"""Unit-тесты AutoAllocatorConfig (SETUP-12 / T-S12-020)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fe_bot.taxonomy.config import (
    AutoAllocatorConfig,
    TaxonomyConfigError,
    default_config_path,
)

pytestmark = pytest.mark.unit


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return p


class TestDefaults:
    def test_defaults_match_yaml_recommendations(self) -> None:
        cfg = AutoAllocatorConfig()
        assert cfg.max_depth == 3
        assert cfg.classes_per_level == 10
        assert cfg.t_set == 0.60
        assert cfg.min_new_class_conf == 0.65
        assert cfg.sim_reuse == 0.85
        assert cfg.sim_force_merge == 0.70

    def test_frozen_immutable(self) -> None:
        cfg = AutoAllocatorConfig()
        with pytest.raises(Exception):  # noqa: B017 - pydantic frozen error
            cfg.t_set = 0.99  # type: ignore[misc]


class TestLoadActualConfig:
    def test_load_repo_config(self) -> None:
        path = default_config_path()
        assert path.exists(), f"Project config missing at {path}"
        cfg = AutoAllocatorConfig.from_yaml(path)
        # Sanity: defaults сохраняются (YAML отражает рекомендации)
        assert cfg.t_set == 0.60
        assert cfg.sim_reuse == 0.85
        assert cfg.embedding_model == "nomic-embed-text"


class TestFromYaml:
    def test_flat_overrides(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
max_depth: 3
classes_per_level: 10
thresholds:
  T_SET: 0.55
  MIN_NEW_CLASS_CONF: 0.70
  SIM_REUSE: 0.90
  SIM_FORCE_MERGE: 0.65
""",
        )
        cfg = AutoAllocatorConfig.from_yaml(path)
        assert cfg.t_set == 0.55
        assert cfg.sim_reuse == 0.90
        assert cfg.sim_force_merge == 0.65

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            AutoAllocatorConfig.from_yaml(tmp_path / "nope.yaml")

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "not: a: valid: yaml: ::")
        with pytest.raises(TaxonomyConfigError):
            AutoAllocatorConfig.from_yaml(path)

    def test_non_mapping_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, "- 1\n- 2\n")
        with pytest.raises(TaxonomyConfigError, match="mapping"):
            AutoAllocatorConfig.from_yaml(path)

    def test_out_of_range_value_rejected(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            """
thresholds:
  SIM_REUSE: 1.5
""",
        )
        with pytest.raises(TaxonomyConfigError, match="validation failed"):
            AutoAllocatorConfig.from_yaml(path)
