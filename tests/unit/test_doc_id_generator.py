"""Unit-тесты DocIdGenerator (SETUP-05 / T-S05-017)."""

from __future__ import annotations

import pytest

from fe_bot.setup.rag_card_generation.doc_id_generator import (
    DocIdGenerator,
    UnsupportedDocTypeForId,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def gen() -> DocIdGenerator:
    return DocIdGenerator()


class TestBasicGeneration:
    @pytest.mark.parametrize(
        "doc_type,title,expected",
        [
            ("schema_card", "Sensor Schema", "schema.sensor_schema.v1"),
            ("task_card", "Classify Threat", "task.classify_threat.v1"),
            ("analytics_card", "Sensor Analytics", "analytics.sensor_analytics.v1"),
            ("field_definition_card", "Uptime Field", "field.uptime_field.v1"),
            ("feature_pattern_card", "Rolling Window", "pattern.rolling_window.v1"),
            ("validation_rule_card", "Positive Check", "validation.positive_check.v1"),
            ("question_template_card", "Sensor Q", "question.sensor_q.v1"),
        ],
    )
    def test_seven_doc_types(
        self,
        gen: DocIdGenerator,
        doc_type: str,
        title: str,
        expected: str,
    ) -> None:
        assert gen.generate_doc_id(doc_type, title, existing_doc_ids=set()) == expected


class TestCyrillicTransliteration:
    def test_russian_title(self, gen: DocIdGenerator) -> None:
        # "Прогноз нагрузки" → "prognoz_nagruzki".
        result = gen.generate_doc_id("task_card", "Прогноз нагрузки", existing_doc_ids=set())
        assert result == "task.prognoz_nagruzki.v1"

    def test_mixed_alphabet(self, gen: DocIdGenerator) -> None:
        result = gen.generate_doc_id("schema_card", "Тест Schema 2024", existing_doc_ids=set())
        assert result == "schema.test_schema_2024.v1"


class TestVersionBump:
    def test_v2_when_v1_exists(self, gen: DocIdGenerator) -> None:
        result = gen.generate_doc_id(
            "analytics_card",
            "Sensor Analytics",
            existing_doc_ids={"analytics.sensor_analytics.v1"},
        )
        assert result == "analytics.sensor_analytics.v2"

    def test_v3_when_v1_v2_exist(self, gen: DocIdGenerator) -> None:
        result = gen.generate_doc_id(
            "task_card",
            "Foo",
            existing_doc_ids={"task.foo.v1", "task.foo.v2"},
        )
        assert result == "task.foo.v3"

    def test_gap_v2_filled(self, gen: DocIdGenerator) -> None:
        # Если занят v1 и v3, генератор дает v2 (заполняет gap).
        result = gen.generate_doc_id(
            "task_card",
            "Foo",
            existing_doc_ids={"task.foo.v1", "task.foo.v3"},
        )
        assert result == "task.foo.v2"

    def test_other_doc_type_doesnt_conflict(self, gen: DocIdGenerator) -> None:
        # task.foo.v1 не блокирует schema.foo.v1.
        result = gen.generate_doc_id(
            "schema_card",
            "Foo",
            existing_doc_ids={"task.foo.v1"},
        )
        assert result == "schema.foo.v1"


class TestEdgeCases:
    def test_empty_title_unnamed(self, gen: DocIdGenerator) -> None:
        assert (
            gen.generate_doc_id("schema_card", "   !!!  ", existing_doc_ids=set())
            == "schema.unnamed.v1"
        )

    def test_long_title_truncated(self, gen: DocIdGenerator) -> None:
        long_title = "word" * 30
        result = gen.generate_doc_id("schema_card", long_title, existing_doc_ids=set())
        # Извлекаем slug часть: schema.<slug>.v1
        slug_part = result[len("schema.") : -len(".v1")]
        assert len(slug_part) <= 50

    def test_unsupported_doc_type_raises(self, gen: DocIdGenerator) -> None:
        with pytest.raises(UnsupportedDocTypeForId):
            gen.generate_doc_id("ontology_card", "X", existing_doc_ids=set())
