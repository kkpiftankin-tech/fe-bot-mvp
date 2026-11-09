"""Unit-тесты taxonomy retrieval helpers (SETUP-12 / T-S12-060, T-S12-061)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)
from schemas.taxonomy.state import ClassificationState, bit_offset

from fe_bot.taxonomy import (
    BitTest,
    TaxonomyFilter,
    TaxonomyRegistry,
    apply_filter_to_hits,
    build_payload,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    level: int,
    parent_path: str,
    bit_index: int,
    class_slug: str,
) -> TaxonomyBitRegistryEntry:
    return TaxonomyBitRegistryEntry(
        version_id="v1.0.0",
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=f"Класс {class_slug}",
        description=f"Описание {class_slug}.",
        created_at=datetime.now(tz=UTC),
    )


def _make_registry(entries: list[TaxonomyBitRegistryEntry]) -> TaxonomyRegistry:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(
        TaxonomyVersion(
            version_id="v1.0.0",
            created_at=datetime.now(tz=UTC),
            is_active=True,
            entries=entries,
        )
    )
    return reg


@dataclass
class _FakeHit:
    payload: dict[str, Any]


# ----------------------------------------------------------------------
# build_payload
# ----------------------------------------------------------------------


class TestBuildPayload:
    def test_none_state_returns_empty(self) -> None:
        reg = _make_registry([])
        assert build_payload(None, registry=reg) == {}

    def test_full_state(self) -> None:
        reg = _make_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=1, parent_path="task", bit_index=0, class_slug="pvo"
                ),
            ]
        )
        bitmap = (1 << bit_offset(0, 0)) | (1 << bit_offset(1, 0))
        state = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=bitmap,
            primary_l0_idx=0,
            primary_l1_idx=0,
            unknown_at_level=2,
        )
        payload = build_payload(state, registry=reg)
        assert payload["taxonomy_version"] == "v1.0.0"
        assert payload["primary_l0"] == "task"
        assert payload["primary_l1"] == "pvo"
        assert payload["taxonomy_path"] == ["task", "pvo"]
        assert payload["bitmap_l0"] == 1
        assert payload["bitmap_l1"] == 1
        assert payload["bitmap_l2"] == 0
        assert payload["classification_bitmap"] == bitmap
        assert payload["unknown_at_level"] == 2


# ----------------------------------------------------------------------
# TaxonomyFilter exact-match
# ----------------------------------------------------------------------


class TestExactMatchFilters:
    def test_primary_l0_match(self) -> None:
        f = TaxonomyFilter(primary_l0=["task"])
        assert f.matches_payload({"primary_l0": "task"})
        assert not f.matches_payload({"primary_l0": "schema"})

    def test_primary_l0_or(self) -> None:
        f = TaxonomyFilter(primary_l0=["task", "analytics"])
        assert f.matches_payload({"primary_l0": "task"})
        assert f.matches_payload({"primary_l0": "analytics"})
        assert not f.matches_payload({"primary_l0": "schema"})

    def test_primary_l1_match(self) -> None:
        f = TaxonomyFilter(primary_l1=["pvo"])
        assert f.matches_payload({"primary_l1": "pvo"})
        assert not f.matches_payload({"primary_l1": "navigation"})

    def test_taxonomy_version_match(self) -> None:
        f = TaxonomyFilter(taxonomy_version="v1.0.5")
        assert f.matches_payload({"taxonomy_version": "v1.0.5"})
        assert not f.matches_payload({"taxonomy_version": "v1.0.0"})

    def test_empty_filter_matches_all(self) -> None:
        f = TaxonomyFilter()
        assert f.matches_payload({})
        assert f.matches_payload({"primary_l0": "anything"})


class TestPathPrefix:
    def test_exact_prefix(self) -> None:
        f = TaxonomyFilter(path_prefix=["task"])
        assert f.matches_payload({"taxonomy_path": ["task"]})
        assert f.matches_payload({"taxonomy_path": ["task", "pvo"]})
        assert f.matches_payload(
            {"taxonomy_path": ["task", "pvo", "tracking"]}
        )
        assert not f.matches_payload({"taxonomy_path": ["schema"]})

    def test_longer_prefix(self) -> None:
        f = TaxonomyFilter(path_prefix=["task", "pvo"])
        assert f.matches_payload(
            {"taxonomy_path": ["task", "pvo", "tracking"]}
        )
        assert f.matches_payload({"taxonomy_path": ["task", "pvo"]})
        assert not f.matches_payload({"taxonomy_path": ["task"]})
        assert not f.matches_payload(
            {"taxonomy_path": ["task", "navigation"]}
        )

    def test_no_path_in_payload(self) -> None:
        f = TaxonomyFilter(path_prefix=["task"])
        assert not f.matches_payload({})


class TestBitTests:
    def test_any_bit_at_l0(self) -> None:
        f = TaxonomyFilter(any_bit=[BitTest(level=0, bit_in_level=0)])
        payload_with = {"classification_bitmap": 1 << bit_offset(0, 0)}
        payload_without = {"classification_bitmap": 1 << bit_offset(0, 1)}
        assert f.matches_payload(payload_with)
        assert not f.matches_payload(payload_without)

    def test_any_bit_or_semantics(self) -> None:
        f = TaxonomyFilter(
            any_bit=[
                BitTest(level=0, bit_in_level=0),
                BitTest(level=0, bit_in_level=2),
            ]
        )
        # task установлен — пройдёт
        assert f.matches_payload(
            {"classification_bitmap": 1 << bit_offset(0, 0)}
        )
        # analytics установлен — тоже пройдёт
        assert f.matches_payload(
            {"classification_bitmap": 1 << bit_offset(0, 2)}
        )
        # ни task ни analytics — не пройдёт
        assert not f.matches_payload(
            {"classification_bitmap": 1 << bit_offset(0, 1)}
        )

    def test_all_bits_and_semantics(self) -> None:
        f = TaxonomyFilter(
            all_bits=[
                BitTest(level=0, bit_in_level=0),
                BitTest(level=0, bit_in_level=2),
            ]
        )
        # оба установлены
        both = (1 << bit_offset(0, 0)) | (1 << bit_offset(0, 2))
        assert f.matches_payload({"classification_bitmap": both})
        # только один
        assert not f.matches_payload(
            {"classification_bitmap": 1 << bit_offset(0, 0)}
        )


class TestMaxUnknownLevel:
    def test_accepts_full_classification(self) -> None:
        f = TaxonomyFilter(max_unknown_level=2)
        # None = полностью классифицировано → проходит
        assert f.matches_payload({"unknown_at_level": None})
        assert f.matches_payload({})  # отсутствие ключа = None

    def test_accepts_at_max_threshold(self) -> None:
        f = TaxonomyFilter(max_unknown_level=2)
        assert f.matches_payload({"unknown_at_level": 2})
        assert not f.matches_payload({"unknown_at_level": 1})

    def test_strict_filter(self) -> None:
        f = TaxonomyFilter(max_unknown_level=1)
        assert f.matches_payload({"unknown_at_level": 1})
        assert not f.matches_payload({"unknown_at_level": 0})


class TestCombinedCriteria:
    def test_and_semantics(self) -> None:
        # primary_l0=task AND path_prefix=[task, pvo]
        f = TaxonomyFilter(
            primary_l0=["task"],
            path_prefix=["task", "pvo"],
        )
        good = {
            "primary_l0": "task",
            "taxonomy_path": ["task", "pvo", "tracking"],
        }
        assert f.matches_payload(good)
        # primary_l0 не совпал
        bad1 = {
            "primary_l0": "schema",
            "taxonomy_path": ["task", "pvo", "tracking"],
        }
        assert not f.matches_payload(bad1)
        # path не совпал
        bad2 = {
            "primary_l0": "task",
            "taxonomy_path": ["task", "navigation"],
        }
        assert not f.matches_payload(bad2)


class TestPayloadDictConversion:
    def test_exact_only_extracted(self) -> None:
        f = TaxonomyFilter(
            primary_l0=["task"],
            primary_l1=["pvo"],
            taxonomy_version="v1.0.0",
            any_bit=[BitTest(level=0, bit_in_level=3)],  # не выражается
        )
        out = f.to_payload_dict()
        assert "primary_l0" in out
        assert "primary_l1" in out
        assert "taxonomy_version" in out
        # bitmap-критерии не уехали
        assert "any_bit" not in out
        assert "classification_bitmap" not in out

    def test_has_bitwise_criteria(self) -> None:
        f1 = TaxonomyFilter(primary_l0=["task"])
        assert not f1.has_bitwise_criteria
        f2 = TaxonomyFilter(path_prefix=["task"])
        assert f2.has_bitwise_criteria
        f3 = TaxonomyFilter(any_bit=[BitTest(level=0, bit_in_level=0)])
        assert f3.has_bitwise_criteria


class TestApplyFilterToHits:
    def test_filters_hits(self) -> None:
        f = TaxonomyFilter(primary_l0=["task"])
        hits = [
            _FakeHit(payload={"primary_l0": "task"}),
            _FakeHit(payload={"primary_l0": "schema"}),
            _FakeHit(payload={"primary_l0": "task"}),
        ]
        out = apply_filter_to_hits(hits, f)
        assert len(out) == 2
        assert all(h.payload["primary_l0"] == "task" for h in out)

    def test_empty_filter_passes_through(self) -> None:
        f = TaxonomyFilter()
        hits = [_FakeHit(payload={}), _FakeHit(payload={"x": 1})]
        assert len(apply_filter_to_hits(hits, f)) == 2
