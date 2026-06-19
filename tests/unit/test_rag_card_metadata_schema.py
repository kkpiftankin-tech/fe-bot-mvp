"""Unit-тесты RAGCardMetadataDTO (SETUP-05 / T-S05-003)."""

from __future__ import annotations

import pytest
import yaml
from schemas.setup.rag_card_metadata import (
    DEFAULT_METADATA_SCHEMA_VERSION,
    FeatureTableSpec,
    RAGCardMetadataDTO,
    ValidationRuleSpec,
)

pytestmark = pytest.mark.unit


def _front_matter() -> dict[str, object]:
    return {
        "doc_id": "analytics.sensor.v1",
        "doc_type": "analytics_card",
        "title": "Sensor analytics",
        "version": "1.0",
        "status": "generated",
        "source_files": ["analytics.md"],
        "source_sections": ["sec_005"],
        "domain": ["naval"],
        "task_type": ["classification"],
        "data_source": ["radar"],
        "entity_type": ["sensor"],
        "phase": ["feature_synthesis"],
        "agent_targets": ["FeatureSynthesisAgent"],
        "retrieval_tags": ["sensor", "uptime"],
        "feature_tables": [
            {"table_id": "t1", "columns": ["a", "b"]},
        ],
        "validation_rules": [
            {
                "rule_id": "r1",
                "severity": "error",
                "scope": "field",
                "description": "value must be positive",
            }
        ],
    }


class TestConstruction:
    def test_minimal(self) -> None:
        meta = RAGCardMetadataDTO(
            doc_id="analytics.x.v1",
            card_version="1.0",
        )
        assert meta.metadata_schema_version == DEFAULT_METADATA_SCHEMA_VERSION
        assert meta.front_matter == {}
        assert meta.domain == []

    def test_full(self) -> None:
        meta = RAGCardMetadataDTO.from_front_matter_dict(_front_matter())
        assert meta.doc_id == "analytics.sensor.v1"
        assert meta.domain == ["naval"]
        assert len(meta.feature_tables) == 1
        assert meta.feature_tables[0].table_id == "t1"
        assert meta.validation_rules[0].severity == "error"


class TestYAMLRoundtrip:
    def test_to_yaml_front_matter(self) -> None:
        meta = RAGCardMetadataDTO.from_front_matter_dict(_front_matter())
        yaml_str = meta.to_yaml_front_matter()
        assert "doc_id: analytics.sensor.v1" in yaml_str
        # Roundtrip через yaml.safe_load.
        parsed = yaml.safe_load(yaml_str)
        assert parsed["doc_id"] == "analytics.sensor.v1"
        assert parsed["domain"] == ["naval"]


class TestSpecs:
    def test_feature_table_spec(self) -> None:
        ft = FeatureTableSpec(table_id="t1", columns=["a", "b", "c"])
        assert ft.columns == ["a", "b", "c"]

    def test_validation_rule_spec_invalid_severity(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ValidationRuleSpec(
                rule_id="r1",
                severity="critical",  # invalid
                scope="field",
                description="x",
            )

    def test_validation_rule_spec_invalid_scope(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ValidationRuleSpec(
                rule_id="r1",
                severity="error",
                scope="global",  # invalid
                description="x",
            )

    def test_validation_rule_spec_valid(self) -> None:
        vr = ValidationRuleSpec(
            rule_id="r1",
            severity="warning",
            scope="cross_table",
            description="cross-check fields",
        )
        assert vr.severity == "warning"
