"""Unit tests for ValidationSummaryDTO (SETUP-07 / T-S07-002)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.setup.validation_summary import ValidationSummaryDTO


def test_defaults():
    s = ValidationSummaryDTO(setup_job_id="sj1")
    assert s.total == 0
    assert s.by_code == {}


def test_with_counts():
    s = ValidationSummaryDTO(
        setup_job_id="sj1",
        total=10,
        passed=7,
        warnings=2,
        failed=1,
        review_required=3,
        by_code={"UNKNOWN_DOMAIN": 2, "MISSING_TAGS": 1},
        last_run_id="vr_001",
    )
    assert s.passed == 7
    assert s.by_code["UNKNOWN_DOMAIN"] == 2


def test_frozen():
    s = ValidationSummaryDTO(setup_job_id="sj1")
    with pytest.raises(ValidationError):
        s.total = 5  # type: ignore[misc]


def test_negative_count_rejected():
    with pytest.raises(ValidationError):
        ValidationSummaryDTO(setup_job_id="sj1", total=-1)
