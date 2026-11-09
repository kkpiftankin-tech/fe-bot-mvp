"""Unit-тесты TaxonomyFocus (SETUP-12 / T-S12-062)."""

from __future__ import annotations

import pytest

from fe_bot.taxonomy import (
    TaxonomyFocus,
    TaxonomyPathPattern,
    collect_focuses,
)

pytestmark = pytest.mark.unit


class TestPathPatternParse:
    def test_simple(self) -> None:
        p = TaxonomyPathPattern.parse("task")
        assert p.parts == ("task",)
        assert p.is_wildcard is False

    def test_two_levels(self) -> None:
        p = TaxonomyPathPattern.parse("task.pvo")
        assert p.parts == ("task", "pvo")
        assert p.is_wildcard is False

    def test_wildcard(self) -> None:
        p = TaxonomyPathPattern.parse("task.*")
        assert p.parts == ("task",)
        assert p.is_wildcard is True

    def test_two_level_wildcard(self) -> None:
        p = TaxonomyPathPattern.parse("task.pvo.*")
        assert p.parts == ("task", "pvo")
        assert p.is_wildcard is True

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError):
            TaxonomyPathPattern.parse("")
        with pytest.raises(ValueError):
            TaxonomyPathPattern.parse("   ")

    def test_bare_wildcard_rejected(self) -> None:
        with pytest.raises(ValueError, match="Bare"):
            TaxonomyPathPattern.parse(".*")


class TestPathPatternMatches:
    def test_exact_match(self) -> None:
        p = TaxonomyPathPattern.parse("task")
        assert p.matches(["task"])
        assert not p.matches(["task", "pvo"])  # not wildcard
        assert not p.matches(["schema"])
        assert not p.matches([])

    def test_wildcard_match(self) -> None:
        p = TaxonomyPathPattern.parse("task.*")
        assert p.matches(["task"])
        assert p.matches(["task", "pvo"])
        assert p.matches(["task", "pvo", "tracking"])
        assert not p.matches(["schema"])

    def test_deep_wildcard(self) -> None:
        p = TaxonomyPathPattern.parse("task.pvo.*")
        assert p.matches(["task", "pvo"])
        assert p.matches(["task", "pvo", "tracking"])
        assert not p.matches(["task"])
        assert not p.matches(["task", "navigation"])


class TestFocusMatching:
    def test_empty_includes_passes_everything(self) -> None:
        f = TaxonomyFocus()
        assert f.matches_path(["task", "pvo"])
        assert f.matches_path([])

    def test_include_only(self) -> None:
        f = TaxonomyFocus(include_paths=("task.*",))
        assert f.matches_path(["task"])
        assert f.matches_path(["task", "pvo"])
        assert not f.matches_path(["schema"])

    def test_multiple_includes(self) -> None:
        f = TaxonomyFocus(include_paths=("task.*", "schema.*"))
        assert f.matches_path(["task"])
        assert f.matches_path(["schema", "etl"])
        assert not f.matches_path(["analytics"])

    def test_exclude_overrides_include(self) -> None:
        f = TaxonomyFocus(
            include_paths=("task.*",),
            exclude_paths=("task.pvo.*",),
        )
        assert f.matches_path(["task"])
        assert f.matches_path(["task", "navigation"])
        # pvo и его дети исключены
        assert not f.matches_path(["task", "pvo"])
        assert not f.matches_path(["task", "pvo", "tracking"])

    def test_payload_matching(self) -> None:
        f = TaxonomyFocus(include_paths=("task.*",))
        assert f.matches_payload({"taxonomy_path": ["task", "pvo"]})
        assert not f.matches_payload({"taxonomy_path": ["schema"]})
        # без path — не проходит (пустой path не matches "task.*")
        assert not f.matches_payload({})


class TestToFilter:
    def test_simple_to_path_prefix(self) -> None:
        f = TaxonomyFocus(include_paths=("task.*",))
        flt = f.to_filter()
        assert flt.path_prefix == ["task"]

    def test_two_level(self) -> None:
        f = TaxonomyFocus(include_paths=("task.pvo",))
        flt = f.to_filter()
        assert flt.path_prefix == ["task", "pvo"]

    def test_multiple_includes_falls_back_to_empty(self) -> None:
        # Сложные случаи (несколько include) → пустой filter; вызывающий
        # код должен использовать matches_payload как post-filter.
        f = TaxonomyFocus(include_paths=("task.*", "schema.*"))
        flt = f.to_filter()
        assert flt.path_prefix == []

    def test_excludes_block_filter_conversion(self) -> None:
        f = TaxonomyFocus(
            include_paths=("task.*",),
            exclude_paths=("task.pvo",),
        )
        flt = f.to_filter()
        assert flt.path_prefix == []

    def test_empty_focus(self) -> None:
        f = TaxonomyFocus()
        flt = f.to_filter()
        assert flt.path_prefix == []


class TestCollectFocuses:
    def test_union(self) -> None:
        a = TaxonomyFocus(include_paths=("task.*",))
        b = TaxonomyFocus(
            include_paths=("schema.*",),
            exclude_paths=("schema.draft",),
        )
        merged = collect_focuses(a, b)
        assert merged.include_paths == ("task.*", "schema.*")
        assert merged.exclude_paths == ("schema.draft",)
        # Проверим semantics
        assert merged.matches_path(["task"])
        assert merged.matches_path(["schema", "etl"])
        assert not merged.matches_path(["schema", "draft"])
