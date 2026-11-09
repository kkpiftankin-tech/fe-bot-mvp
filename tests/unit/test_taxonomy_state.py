"""Unit-тесты schemas.taxonomy.state (SETUP-12 / T-S12-001).

Покрывает:
- bit-offset arithmetic и маски.
- Инварианты ClassificationState (bitmap_in_range, primary_consistency,
  cascading_unknown).
- AutoCreationRecord validation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.state import (
    BIT_MASK_ALL,
    BIT_MASK_L0,
    BIT_MASK_L1,
    BIT_MASK_L2,
    AutoCreationRecord,
    ClassificationState,
    bit_offset,
    bits_set_at_level,
    level_mask,
)

pytestmark = pytest.mark.unit


class TestBitOffsetAndMasks:
    def test_bit_offset_l0(self) -> None:
        assert bit_offset(0, 0) == 0
        assert bit_offset(0, 9) == 9

    def test_bit_offset_l1(self) -> None:
        assert bit_offset(1, 0) == 10
        assert bit_offset(1, 9) == 19

    def test_bit_offset_l2(self) -> None:
        assert bit_offset(2, 0) == 20
        assert bit_offset(2, 9) == 29

    def test_bit_offset_invalid_level(self) -> None:
        with pytest.raises(ValueError):
            bit_offset(3, 0)
        with pytest.raises(ValueError):
            bit_offset(-1, 0)

    def test_bit_offset_invalid_bit(self) -> None:
        with pytest.raises(ValueError):
            bit_offset(0, 10)
        with pytest.raises(ValueError):
            bit_offset(0, -1)

    def test_masks_non_overlapping(self) -> None:
        assert BIT_MASK_L0 & BIT_MASK_L1 == 0
        assert BIT_MASK_L0 & BIT_MASK_L2 == 0
        assert BIT_MASK_L1 & BIT_MASK_L2 == 0

    def test_masks_cover_30_bits(self) -> None:
        assert BIT_MASK_ALL == BIT_MASK_L0 | BIT_MASK_L1 | BIT_MASK_L2
        assert BIT_MASK_ALL == 0x3FFFFFFF  # bits 0..29

    def test_level_mask(self) -> None:
        assert level_mask(0) == BIT_MASK_L0
        assert level_mask(1) == BIT_MASK_L1
        assert level_mask(2) == BIT_MASK_L2


class TestBitsSetAtLevel:
    def test_empty_bitmap(self) -> None:
        assert bits_set_at_level(0, 0) == []
        assert bits_set_at_level(0, 1) == []

    def test_single_bit_l0(self) -> None:
        bitmap = 1 << 3  # bit 3 of L0
        assert bits_set_at_level(bitmap, 0) == [3]
        assert bits_set_at_level(bitmap, 1) == []

    def test_single_bit_l1(self) -> None:
        bitmap = 1 << 10  # bit 0 of L1
        assert bits_set_at_level(bitmap, 1) == [0]
        assert bits_set_at_level(bitmap, 0) == []

    def test_multi_bits_l0(self) -> None:
        bitmap = (1 << 0) | (1 << 3) | (1 << 7)
        assert bits_set_at_level(bitmap, 0) == [0, 3, 7]


class TestClassificationStateBasic:
    def _make(self, **overrides: object) -> ClassificationState:
        defaults: dict[str, object] = {
            "taxonomy_version_id": "v1.0.0",
        }
        defaults.update(overrides)
        return ClassificationState(**defaults)  # type: ignore[arg-type]

    def test_empty_state_is_valid(self) -> None:
        st = self._make()
        assert st.classification_bitmap == 0
        assert st.primary_l0_idx is None
        assert st.primary_l1_idx is None
        assert st.unknown_at_level is None
        assert st.is_classified is False
        assert st.depth_reached == -1

    def test_single_l0_bit(self) -> None:
        st = self._make(
            classification_bitmap=(1 << 0),
            primary_l0_idx=0,
        )
        assert st.is_classified is True
        assert st.depth_reached == 0
        assert st.bits_at(0) == [0]

    def test_full_3_levels(self) -> None:
        bitmap = (1 << 0) | (1 << 10) | (1 << 20)
        st = self._make(
            classification_bitmap=bitmap,
            primary_l0_idx=0,
            primary_l1_idx=0,
        )
        assert st.depth_reached == 2
        assert st.bits_at(0) == [0]
        assert st.bits_at(1) == [0]
        assert st.bits_at(2) == [0]


class TestClassificationStateInvariants:
    def test_bitmap_outside_30_bit_zone_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClassificationState(
                taxonomy_version_id="v1.0.0",
                classification_bitmap=(1 << 30),
            )

    def test_primary_l0_must_be_set_bit(self) -> None:
        with pytest.raises(ValueError, match="primary_l0_idx"):
            ClassificationState(
                taxonomy_version_id="v1.0.0",
                classification_bitmap=(1 << 1),  # bit 1 set
                primary_l0_idx=0,  # but pointing at bit 0
            )

    def test_primary_l1_requires_primary_l0(self) -> None:
        with pytest.raises(ValueError, match="primary_l1_idx requires"):
            ClassificationState(
                taxonomy_version_id="v1.0.0",
                classification_bitmap=(1 << 10),
                primary_l1_idx=0,
            )

    def test_primary_l1_must_be_set_bit(self) -> None:
        with pytest.raises(ValueError, match="primary_l1_idx"):
            ClassificationState(
                taxonomy_version_id="v1.0.0",
                classification_bitmap=(1 << 0) | (1 << 11),
                primary_l0_idx=0,
                primary_l1_idx=0,  # pointing at L1 bit 0, but L1 bit 1 set
            )


class TestCascadingUnknownInvariant:
    def test_unknown_at_l0_forbids_any_bits(self) -> None:
        with pytest.raises(ValueError, match="level 0"):
            ClassificationState(
                taxonomy_version_id="v1.0.0",
                classification_bitmap=(1 << 0),
                unknown_at_level=0,
            )

    def test_unknown_at_l0_forbids_primary_l0(self) -> None:
        with pytest.raises(ValueError, match="primary_l0_idx"):
            ClassificationState(
                taxonomy_version_id="v1.0.0",
                primary_l0_idx=0,
                unknown_at_level=0,
            )

    def test_unknown_at_l1_forbids_l1_l2_bits(self) -> None:
        with pytest.raises(ValueError, match="level 1"):
            ClassificationState(
                taxonomy_version_id="v1.0.0",
                classification_bitmap=(1 << 0) | (1 << 10),
                primary_l0_idx=0,
                unknown_at_level=1,
            )

    def test_unknown_at_l1_allows_l0_bits(self) -> None:
        st = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=(1 << 0),
            primary_l0_idx=0,
            unknown_at_level=1,
        )
        assert st.primary_l1_idx is None
        assert st.bits_at(1) == []
        assert st.bits_at(2) == []

    def test_unknown_at_l2_allows_l0_l1_bits(self) -> None:
        st = ClassificationState(
            taxonomy_version_id="v1.0.0",
            classification_bitmap=(1 << 0) | (1 << 10),
            primary_l0_idx=0,
            primary_l1_idx=0,
            unknown_at_level=2,
        )
        assert st.bits_at(0) == [0]
        assert st.bits_at(1) == [0]
        assert st.bits_at(2) == []


class TestAutoCreationRecord:
    def test_valid_record(self) -> None:
        rec = AutoCreationRecord(
            level=1,
            parent_path="task",
            bit_index=0,
            class_slug="pvo",
            triggered_by_section_id="sec_abc",
            created_at=datetime.now(tz=UTC),
            similarity_to_closest=0.45,
            closest_existing_slug="navigation",
        )
        assert rec.class_slug == "pvo"
        assert rec.parent_path == "task"

    def test_invalid_slug_rejected(self) -> None:
        with pytest.raises(ValueError):
            AutoCreationRecord(
                level=1,
                parent_path="task",
                bit_index=0,
                class_slug="UPPERCASE",  # not kebab-case
                triggered_by_section_id="sec_abc",
                created_at=datetime.now(tz=UTC),
            )

    def test_similarity_in_range(self) -> None:
        with pytest.raises(ValueError):
            AutoCreationRecord(
                level=1,
                parent_path="task",
                bit_index=0,
                class_slug="pvo",
                triggered_by_section_id="sec_abc",
                created_at=datetime.now(tz=UTC),
                similarity_to_closest=1.5,  # out of [0, 1]
            )
