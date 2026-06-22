"""Unit-тесты OntologyMapper (SETUP-05 / T-S05-013)."""

from __future__ import annotations

import pytest

from fe_bot.setup.rag_card_generation.ontology_mapper import (
    OntologyMapper,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mapper() -> OntologyMapper:
    return OntologyMapper()


class TestVersion:
    def test_version(self, mapper: OntologyMapper) -> None:
        assert mapper.ontology_version == "ontology_v1"


class TestCanonicalLookup:
    def test_domain_canonical_returns_self(self, mapper: OntologyMapper) -> None:
        result = mapper.normalize_domain("naval")
        assert result.canonical == "naval"
        assert result.warnings == []

    def test_domain_case_insensitive(self, mapper: OntologyMapper) -> None:
        assert mapper.normalize_domain("NAVAL").canonical == "naval"
        assert mapper.normalize_domain("  naval  ").canonical == "naval"

    def test_domain_russian_synonym(self, mapper: OntologyMapper) -> None:
        result = mapper.normalize_domain("морской")
        assert result.canonical == "naval"
        assert result.warnings == []

    def test_phase_canonical(self, mapper: OntologyMapper) -> None:
        # Если "feature_synthesis" есть в phase values.
        assert mapper.normalize_phase("feature_synthesis").canonical == "feature_synthesis"

    def test_agent_pascal_case(self, mapper: OntologyMapper) -> None:
        # agent_targets — PascalCase, canonical = "FeatureSynthesisAgent".
        result = mapper.normalize_agent_targets("FeatureSynthesisAgent")
        assert result.canonical == "FeatureSynthesisAgent"


class TestUnknownTerm:
    def test_unknown_returns_warning(self, mapper: OntologyMapper) -> None:
        result = mapper.normalize_domain("kitchen")
        assert result.canonical is None
        assert len(result.warnings) == 1
        w = result.warnings[0]
        assert w.code == "ONTOLOGY_UNKNOWN_TERM"
        assert w.field == "domain"

    def test_empty_value_warning(self, mapper: OntologyMapper) -> None:
        result = mapper.normalize_domain("")
        assert result.canonical is None
        assert result.warnings[0].code == "ONTOLOGY_EMPTY_VALUE"

    def test_whitespace_only_warning(self, mapper: OntologyMapper) -> None:
        assert mapper.normalize_domain("   ").warnings[0].code == "ONTOLOGY_EMPTY_VALUE"


class TestListNormalize:
    def test_mixed_known_and_unknown(self, mapper: OntologyMapper) -> None:
        canonicals, warnings = mapper.normalize_list("domain", ["naval", "xyz", "морской"])
        # naval + naval (через синоним) — два значения, xyz — warning.
        assert "naval" in canonicals
        assert len(warnings) == 1
        assert warnings[0].raw_value == "xyz"

    def test_all_known(self, mapper: OntologyMapper) -> None:
        canonicals, warnings = mapper.normalize_list("phase", ["feature_synthesis", "validation"])
        assert set(canonicals) == {"feature_synthesis", "validation"}
        assert warnings == []


class TestValidateCardMetadata:
    def test_clean_metadata_no_warnings(self, mapper: OntologyMapper) -> None:
        meta = {
            "domain": ["naval"],
            "phase": ["feature_synthesis"],
            "agent_targets": ["FeatureSynthesisAgent"],
        }
        assert mapper.validate_card_metadata(meta) == []

    def test_unknown_terms_produce_warnings(self, mapper: OntologyMapper) -> None:
        meta = {
            "domain": ["naval", "kitchen"],
            "phase": ["unknown_phase"],
        }
        warnings = mapper.validate_card_metadata(meta)
        assert len(warnings) == 2
        codes = {w.code for w in warnings}
        assert codes == {"ONTOLOGY_UNKNOWN_TERM"}


class TestErrors:
    def test_unknown_field_raises(self, mapper: OntologyMapper) -> None:
        with pytest.raises(ValueError, match="Unknown ontology field"):
            mapper.normalize("not_a_field", "x")


class TestAllowedValues:
    def test_allowed_values_returns_set(self, mapper: OntologyMapper) -> None:
        domains = mapper.allowed_values("domain")
        assert "naval" in domains
        assert isinstance(domains, set)
