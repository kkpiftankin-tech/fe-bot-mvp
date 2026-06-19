"""RAGCardMetadataDTO (SETUP-05) — типизированный YAML front matter RAG-карточки.

Ontology-validated metadata + doc-type-specific поля. Сериализуется в YAML
для Markdown artifact и используется retrieval-фильтрами в SETUP-09/runtime.

Source of truth — docs/06-rag/metadata-schema.md, docs/03-architecture/services/
data-transfer-objects.md DTO-61.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_METADATA_SCHEMA_VERSION = "rag_metadata_v1"


class FeatureTableSpec(BaseModel):
    """Спецификация feature table для schema_card / analytics_card."""

    model_config = ConfigDict(extra="forbid")

    table_id: str = Field(..., min_length=1)
    columns: list[str] = Field(default_factory=list)


class ValidationRuleSpec(BaseModel):
    """Спецификация validation rule для validation_rule_card."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., min_length=1)
    severity: str = Field(
        ...,
        description="error | warning | info",
        pattern=r"^(error|warning|info)$",
    )
    scope: str = Field(
        ...,
        description="field | row | table | cross_table",
        pattern=r"^(field|row|table|cross_table)$",
    )
    description: str = Field(..., min_length=1)


class RAGCardMetadataDTO(BaseModel):
    """Типизированный front matter RAG-карточки.

    Required common fields (per docs/06-rag/metadata-schema.md §3):
        doc_id, doc_type, title, version, status, source_files,
        source_sections, domain, phase, retrieval_tags.

    Optional common fields (§4):
        task_type, data_source, entity_type, agent_targets,
        required_input_fields, output_fields, feature_tables,
        validation_rules, compatible_models, owner, last_verified_at.

    Doc-type-specific поля (§5) хранятся в ``front_matter`` dict для гибкости —
    типизация enforced на уровне prompt template + ontology mapper.

    Storage: PostgreSQL `rag_card_metadata` (план), MVP in-memory + snapshot.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # --- identity ---
    doc_id: str = Field(..., min_length=1)
    card_version: str = Field(..., pattern=r"^\d+(\.\d+){0,2}$")
    metadata_schema_version: str = Field(default=DEFAULT_METADATA_SCHEMA_VERSION)

    # --- raw front matter dict (for full YAML roundtrip incl. doc-type-specific) ---
    front_matter: dict[str, Any] = Field(default_factory=dict)

    # --- typed common required ---
    domain: list[str] = Field(default_factory=list)
    phase: list[str] = Field(default_factory=list)
    retrieval_tags: list[str] = Field(default_factory=list)

    # --- typed common optional ---
    task_type: list[str] = Field(default_factory=list)
    data_source: list[str] = Field(default_factory=list)
    entity_type: list[str] = Field(default_factory=list)
    agent_targets: list[str] = Field(default_factory=list)
    required_input_fields: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    feature_tables: list[FeatureTableSpec] = Field(default_factory=list)
    validation_rules: list[ValidationRuleSpec] = Field(default_factory=list)
    compatible_models: list[str] = Field(default_factory=list)
    owner: str | None = None
    last_verified_at: datetime | None = None

    # ----- helpers -----

    def to_yaml_front_matter(self) -> str:
        """Serialize ``front_matter`` dict to YAML (deterministic key order)."""
        buf = io.StringIO()
        yaml.safe_dump(
            self.front_matter,
            buf,
            sort_keys=True,
            allow_unicode=True,
            default_flow_style=False,
        )
        return buf.getvalue()

    @classmethod
    def from_front_matter_dict(
        cls,
        front_matter: dict[str, Any],
        *,
        card_version: str = "1.0",
        metadata_schema_version: str = DEFAULT_METADATA_SCHEMA_VERSION,
    ) -> RAGCardMetadataDTO:
        """Build DTO from raw YAML dict; copies typed fields из front_matter."""
        doc_id = str(front_matter.get("doc_id") or "")
        kwargs: dict[str, Any] = {
            "doc_id": doc_id,
            "card_version": card_version,
            "metadata_schema_version": metadata_schema_version,
            "front_matter": dict(front_matter),
        }
        # Copy typed scalar/list fields if present.
        for key in (
            "domain",
            "phase",
            "retrieval_tags",
            "task_type",
            "data_source",
            "entity_type",
            "agent_targets",
            "required_input_fields",
            "output_fields",
            "compatible_models",
        ):
            value = front_matter.get(key)
            if isinstance(value, list):
                kwargs[key] = [str(v) for v in value]
        owner = front_matter.get("owner")
        if isinstance(owner, str):
            kwargs["owner"] = owner
        # Feature tables and validation rules — structured.
        ft_raw = front_matter.get("feature_tables")
        if isinstance(ft_raw, list):
            kwargs["feature_tables"] = [
                FeatureTableSpec.model_validate(item) for item in ft_raw if isinstance(item, dict)
            ]
        vr_raw = front_matter.get("validation_rules")
        if isinstance(vr_raw, list):
            kwargs["validation_rules"] = [
                ValidationRuleSpec.model_validate(item) for item in vr_raw if isinstance(item, dict)
            ]
        return cls(**kwargs)
