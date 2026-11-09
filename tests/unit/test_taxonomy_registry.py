"""Unit-тесты schemas.taxonomy.registry (SETUP-12 / T-S12-001)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyBitStatus,
    TaxonomyVersion,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    level: int = 0,
    parent_path: str = "",
    bit_index: int = 0,
    class_slug: str = "task",
    version_id: str = "v1.0.0",
    **overrides: object,
) -> TaxonomyBitRegistryEntry:
    defaults: dict[str, object] = {
        "version_id": version_id,
        "level": level,
        "parent_path": parent_path,
        "bit_index": bit_index,
        "class_slug": class_slug,
        "display_name_ru": "Задача",
        "description": "Описание класса.",
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    return TaxonomyBitRegistryEntry(**defaults)  # type: ignore[arg-type]


class TestParentPathConsistency:
    def test_l0_has_empty_parent(self) -> None:
        _entry(level=0, parent_path="")  # ok

    def test_l0_with_parent_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty parent_path"):
            _entry(level=0, parent_path="something")

    def test_l1_requires_parent(self) -> None:
        with pytest.raises(ValueError, match="non-empty parent_path"):
            _entry(level=1, parent_path="")

    def test_l1_single_slug(self) -> None:
        _entry(level=1, parent_path="task")  # ok

    def test_l1_with_dot_rejected(self) -> None:
        with pytest.raises(ValueError, match="single slug"):
            _entry(level=1, parent_path="task.pvo")

    def test_l2_two_slugs(self) -> None:
        _entry(level=2, parent_path="task.pvo")  # ok

    def test_l2_wrong_format_rejected(self) -> None:
        with pytest.raises(ValueError, match="l0_slug.*l1_slug"):
            _entry(level=2, parent_path="task")
        with pytest.raises(ValueError, match="l0_slug.*l1_slug"):
            _entry(level=2, parent_path="task.pvo.tracking")


class TestSlugFormat:
    def test_kebab_case_ok(self) -> None:
        _entry(class_slug="task-pvo-tracking")

    def test_underscore_ok(self) -> None:
        _entry(class_slug="task_card")

    def test_uppercase_rejected(self) -> None:
        with pytest.raises(ValueError):
            _entry(class_slug="TaskCard")

    def test_starts_with_dash_rejected(self) -> None:
        with pytest.raises(ValueError):
            _entry(class_slug="-task")


class TestStatusInvariant:
    def test_active_no_merge_field(self) -> None:
        _entry(status=TaxonomyBitStatus.ACTIVE)

    def test_active_with_merge_field_rejected(self) -> None:
        with pytest.raises(ValueError, match="merged_into_slug"):
            _entry(
                status=TaxonomyBitStatus.ACTIVE,
                merged_into_slug="other",
            )

    def test_deprecated_requires_merge_target(self) -> None:
        with pytest.raises(ValueError, match="merged_into_slug"):
            _entry(status=TaxonomyBitStatus.DEPRECATED_MERGED)

    def test_deprecated_with_merge_target_ok(self) -> None:
        _entry(
            status=TaxonomyBitStatus.DEPRECATED_MERGED,
            merged_into_slug="task_alt",
        )


class TestVersionIdFormat:
    def test_semver_ok(self) -> None:
        _entry(version_id="v1.0.0")
        _entry(version_id="v12.345.67")

    def test_missing_v_prefix_rejected(self) -> None:
        with pytest.raises(ValueError):
            _entry(version_id="1.0.0")

    def test_non_semver_rejected(self) -> None:
        with pytest.raises(ValueError):
            _entry(version_id="v1.0")


class TestTaxonomyVersion:
    def test_empty_version_ok(self) -> None:
        v = TaxonomyVersion(
            version_id="v1.0.0",
            created_at=datetime.now(tz=UTC),
            entries=[],
        )
        assert v.version_id == "v1.0.0"

    def test_entries_must_share_version(self) -> None:
        with pytest.raises(ValueError, match="version_id"):
            TaxonomyVersion(
                version_id="v1.0.0",
                created_at=datetime.now(tz=UTC),
                entries=[_entry(version_id="v2.0.0")],
            )

    def test_duplicate_bit_position_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate bit position"):
            TaxonomyVersion(
                version_id="v1.0.0",
                created_at=datetime.now(tz=UTC),
                entries=[
                    _entry(bit_index=0, class_slug="task"),
                    _entry(bit_index=0, class_slug="other"),
                ],
            )

    def test_duplicate_slug_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate class_slug"):
            TaxonomyVersion(
                version_id="v1.0.0",
                created_at=datetime.now(tz=UTC),
                entries=[
                    _entry(bit_index=0, class_slug="task"),
                    _entry(bit_index=1, class_slug="task"),
                ],
            )

    def test_different_parent_paths_can_have_same_slug(self) -> None:
        # bit_index=0 под "task" и под "schema" — допустимо
        TaxonomyVersion(
            version_id="v1.0.0",
            created_at=datetime.now(tz=UTC),
            entries=[
                _entry(level=1, parent_path="task", bit_index=0, class_slug="pvo"),
                _entry(level=1, parent_path="schema", bit_index=0, class_slug="pvo"),
            ],
        )
