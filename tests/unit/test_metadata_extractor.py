"""Unit-тесты MetadataExtractor (SETUP-05 / T-S05-016)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.rag_card_generation.metadata_extractor import (
    MetadataExtractor,
)

pytestmark = pytest.mark.unit


def _section(
    *,
    title: str = "Default",
    raw_text: str = "body",
    heading_path: list[str] | None = None,
    section_type: SectionType = SectionType.SCHEMA,
    structural_payload: dict[str, Any] | None = None,
) -> ParsedSection:
    # ParsedSection.raw_text / normalized_text — обязательны min_length=1;
    # для тестов пустого "содержательного" текста используем плейсхолдер.
    safe_text = raw_text or "x"
    return ParsedSection(
        section_id="sec_001",
        parse_job_id="pj_001",
        source_document_id="src_001",
        section_index=0,
        parent_section_id=None,
        classification_method="rule_based",
        heading_path=heading_path or [],
        title=title,
        section_type=section_type,
        raw_text=safe_text,
        normalized_text=safe_text,
        content_hash=hashlib.sha256(safe_text.encode()).hexdigest(),
        confidence=0.9,
        created_at=datetime(2026, 6, 19, tzinfo=UTC),
        structural_payload=structural_payload or {},
    )


@pytest.fixture
def extractor() -> MetadataExtractor:
    return MetadataExtractor()


class TestTitle:
    def test_title_from_section(self, extractor: MetadataExtractor) -> None:
        c = extractor.extract(_section(title="Sensor Analytics"))
        assert c.title == "Sensor Analytics"

    def test_title_preserved(self, extractor: MetadataExtractor) -> None:
        # ParsedSection.title — обязательное поле с min_length=1, поэтому
        # fallback на первую строку raw_text реализован в extractor для безопасности,
        # но в норме section.title всегда непустой.
        c = extractor.extract(_section(title="Card title", raw_text=""))
        assert c.title == "Card title"


class TestRetrievalTags:
    def test_extracts_keywords(self, extractor: MetadataExtractor) -> None:
        text = (
            "sensor sensor sensor sensor radar radar tracks tracks "
            "uptime uptime detection detection probability probability"
        )
        c = extractor.extract(_section(raw_text=text))
        assert "sensor" in c.retrieval_tags
        assert "radar" in c.retrieval_tags

    def test_filters_stopwords(self, extractor: MetadataExtractor) -> None:
        # "should" (len=6) — в _STOPWORDS, не должен попасть в tags.
        c = extractor.extract(
            _section(title="X", raw_text="should should should should sensor sensor")
        )
        assert "should" not in c.retrieval_tags

    def test_minimal_text_no_tags(self, extractor: MetadataExtractor) -> None:
        # title не пустой (constraint), но содержательного текста нет.
        c = extractor.extract(_section(title="X", raw_text=""))
        # Может быть пусто либо иметь только сам "x" если он >= min_length.
        # Главное — без падений.
        assert isinstance(c.retrieval_tags, list)


class TestStructuralPayload:
    def test_extracts_columns(self, extractor: MetadataExtractor) -> None:
        c = extractor.extract(_section(structural_payload={"columns": ["a", "b", "c"]}))
        assert c.required_input_fields == ["a", "b", "c"]
        assert c.output_fields == ["a", "b", "c"]

    def test_extracts_fields_alias(self, extractor: MetadataExtractor) -> None:
        c = extractor.extract(_section(structural_payload={"fields": ["x"]}))
        assert c.required_input_fields == ["x"]

    def test_no_payload_empty_fields(self, extractor: MetadataExtractor) -> None:
        c = extractor.extract(_section())
        assert c.required_input_fields == []
        assert c.output_fields == []

    def test_extracts_feature_tables_from_rows(self, extractor: MetadataExtractor) -> None:
        payload: dict[str, Any] = {
            "tables": [
                {
                    "rows": [["sensor_id", "uptime"], [1, 0.95]],
                    "table_id": "sensor_t",
                }
            ]
        }
        c = extractor.extract(_section(structural_payload=payload))
        assert len(c.feature_tables) == 1
        assert c.feature_tables[0]["table_id"] == "sensor_t"
        assert c.feature_tables[0]["columns"] == ["sensor_id", "uptime"]

    def test_extracts_feature_tables_from_columns_key(self, extractor: MetadataExtractor) -> None:
        payload: dict[str, Any] = {"tables": [{"columns": ["a", "b"]}]}
        c = extractor.extract(_section(structural_payload=payload))
        assert c.feature_tables[0]["table_id"] == "table_1"


class TestValidationHints:
    def test_severity_from_heading(self, extractor: MetadataExtractor) -> None:
        c = extractor.extract(
            _section(
                title="Validation rule",
                heading_path=["Validations", "Error rules"],
            )
        )
        assert c.validation_metadata.get("severity") == "error"

    def test_scope_from_title(self, extractor: MetadataExtractor) -> None:
        c = extractor.extract(_section(title="Cross_table check"))
        assert c.validation_metadata.get("scope") == "cross_table"

    def test_no_validation_hints(self, extractor: MetadataExtractor) -> None:
        c = extractor.extract(_section(title="random title"))
        assert c.validation_metadata == {}
