"""Unit tests for ReviewDecisionRepository (SETUP-06 / T-S06-007)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.review_decision import ReviewDecision, ReviewDecisionDTO

from fe_bot.setup.card_review.decision_repository import (
    InMemoryReviewDecisionRepository,
    ReviewDecisionNotFoundError,
)


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(rid: str = "rd_1", **kw: object) -> ReviewDecisionDTO:
    defaults: dict[str, object] = {
        "review_decision_id": rid,
        "setup_job_id": "setup_1",
        "doc_id": "schema.x.v1",
        "card_version": "1.0",
        "decision": ReviewDecision.APPROVE,
        "reviewer_id": "u1",
        "reviewer_role": "user",
        "created_at": _now(),
    }
    defaults.update(kw)
    return ReviewDecisionDTO(**defaults)  # type: ignore[arg-type]


def test_add_and_get():
    repo = InMemoryReviewDecisionRepository()
    d = _make()
    repo.add(d)
    assert repo.get("rd_1") == d


def test_add_idempotent():
    repo = InMemoryReviewDecisionRepository()
    d1 = _make(comment="first")
    d2 = _make(comment="second")  # same rd_1
    repo.add(d1)
    result = repo.add(d2)
    assert result.comment == "first"  # original preserved


def test_get_missing_raises():
    repo = InMemoryReviewDecisionRepository()
    with pytest.raises(ReviewDecisionNotFoundError):
        repo.get("missing")


def test_exists():
    repo = InMemoryReviewDecisionRepository()
    repo.add(_make())
    assert repo.exists("rd_1")
    assert not repo.exists("rd_x")


def test_list_for_card():
    repo = InMemoryReviewDecisionRepository()
    repo.add(_make("rd_1", doc_id="a.v1"))
    repo.add(_make("rd_2", doc_id="a.v1"))
    repo.add(_make("rd_3", doc_id="b.v1"))
    assert {d.review_decision_id for d in repo.list_for_card("a.v1")} == {"rd_1", "rd_2"}


def test_list_for_setup_job():
    repo = InMemoryReviewDecisionRepository()
    repo.add(_make("rd_1", setup_job_id="s1"))
    repo.add(_make("rd_2", setup_job_id="s2"))
    assert len(repo.list_for_setup_job("s1")) == 1


def test_list_for_reviewer():
    repo = InMemoryReviewDecisionRepository()
    repo.add(_make("rd_1", reviewer_id="u1"))
    repo.add(_make("rd_2", reviewer_id="u2"))
    repo.add(_make("rd_3", reviewer_id="u1"))
    assert len(repo.list_for_reviewer("u1")) == 2


def test_snapshot_restore_roundtrip():
    repo = InMemoryReviewDecisionRepository()
    repo.add(_make("rd_1"))
    repo.add(_make("rd_2"))
    data = repo.snapshot()

    repo2 = InMemoryReviewDecisionRepository()
    repo2.restore(data)
    assert repo2.exists("rd_1")
    assert repo2.exists("rd_2")


def test_clear():
    repo = InMemoryReviewDecisionRepository()
    repo.add(_make())
    repo.clear()
    assert not repo.exists("rd_1")
