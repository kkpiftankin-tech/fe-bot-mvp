"""Unit-тесты InMemoryTaxonomyVersionRepository (SETUP-12 / T-S12-011)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.registry import TaxonomyVersion

from fe_bot.taxonomy.version_repository import (
    DuplicateTaxonomyVersionError,
    InMemoryTaxonomyVersionRepository,
    TaxonomyVersionNotFoundError,
)

pytestmark = pytest.mark.unit


def _v(version_id: str = "v1.0.0", *, is_active: bool = True) -> TaxonomyVersion:
    return TaxonomyVersion(
        version_id=version_id,
        created_at=datetime.now(tz=UTC),
        is_active=is_active,
        entries=[],
    )


class TestCreateAndGet:
    def test_create_and_get(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        repo.create(_v())
        out = repo.get("v1.0.0")
        assert out.version_id == "v1.0.0"

    def test_create_duplicate_rejected(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        repo.create(_v())
        with pytest.raises(DuplicateTaxonomyVersionError):
            repo.create(_v())

    def test_get_missing(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        with pytest.raises(TaxonomyVersionNotFoundError):
            repo.get("v9.9.9")


class TestActiveInvariant:
    def test_get_active_none(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        assert repo.get_active() is None

    def test_create_active_version(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        repo.create(_v())
        active = repo.get_active()
        assert active is not None
        assert active.version_id == "v1.0.0"

    def test_create_second_active_deactivates_first(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        repo.create(_v("v1.0.0"))
        repo.create(_v("v1.0.1"))
        active = repo.get_active()
        assert active is not None
        assert active.version_id == "v1.0.1"
        # First should be inactive
        first = repo.get("v1.0.0")
        assert first.is_active is False

    def test_set_active_switches(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        repo.create(_v("v1.0.0"))
        repo.create(_v("v1.0.1"))
        repo.set_active("v1.0.0")
        active = repo.get_active()
        assert active is not None
        assert active.version_id == "v1.0.0"

    def test_set_active_missing_rejected(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        with pytest.raises(TaxonomyVersionNotFoundError):
            repo.set_active("v9.9.9")


class TestDeepCopy:
    def test_create_does_not_share_reference(self) -> None:
        repo = InMemoryTaxonomyVersionRepository()
        v = _v()
        repo.create(v)
        # mutating retrieved instance should not affect store
        out = repo.get("v1.0.0")
        out2 = repo.get("v1.0.0")
        assert out is not out2  # deep copy on get
