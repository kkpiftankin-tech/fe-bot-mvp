"""Unit tests for ReviewLogRepository (SETUP-06 / T-S06-008)."""

from __future__ import annotations

from datetime import UTC, datetime

from schemas.setup.review_log import ReviewLogDTO, ReviewLogEventType

from fe_bot.setup.card_review.log_repository import InMemoryReviewLogRepository


def _now() -> datetime:
    return datetime(2026, 6, 23, 12, 0, 0, tzinfo=UTC)


def _make(lid: str = "rl_1", **kw: object) -> ReviewLogDTO:
    defaults: dict[str, object] = {
        "review_log_id": lid,
        "setup_job_id": "s1",
        "doc_id": "schema.x.v1",
        "card_version": "1.0",
        "event_type": ReviewLogEventType.APPROVED,
        "actor_id": "u1",
        "actor_role": "user",
        "message": "ok",
        "created_at": _now(),
    }
    defaults.update(kw)
    return ReviewLogDTO(**defaults)  # type: ignore[arg-type]


def test_append_and_list():
    repo = InMemoryReviewLogRepository()
    repo.append(_make("rl_1"))
    repo.append(_make("rl_2"))
    items = repo.list_for_card("schema.x.v1")
    assert len(items) == 2


def test_chronological_order_preserved():
    repo = InMemoryReviewLogRepository()
    repo.append(_make("rl_a"))
    repo.append(_make("rl_b"))
    repo.append(_make("rl_c"))
    ids = [e.review_log_id for e in repo.list_for_card("schema.x.v1")]
    assert ids == ["rl_a", "rl_b", "rl_c"]


def test_list_with_limit_returns_tail():
    repo = InMemoryReviewLogRepository()
    for i in range(5):
        repo.append(_make(f"rl_{i}"))
    last_two = repo.list_for_card("schema.x.v1", limit=2)
    assert [e.review_log_id for e in last_two] == ["rl_3", "rl_4"]


def test_list_for_setup_job():
    repo = InMemoryReviewLogRepository()
    repo.append(_make("rl_a", setup_job_id="s1"))
    repo.append(_make("rl_b", setup_job_id="s2"))
    assert len(repo.list_for_setup_job("s1")) == 1


def test_count_for_card():
    repo = InMemoryReviewLogRepository()
    repo.append(_make("rl_1", doc_id="a"))
    repo.append(_make("rl_2", doc_id="a"))
    repo.append(_make("rl_3", doc_id="b"))
    assert repo.count_for_card("a") == 2
    assert repo.count_for_card("b") == 1


def test_snapshot_restore():
    repo = InMemoryReviewLogRepository()
    repo.append(_make("rl_1"))
    data = repo.snapshot()
    repo2 = InMemoryReviewLogRepository()
    repo2.restore(data)
    assert repo2.count_for_card("schema.x.v1") == 1


def test_clear():
    repo = InMemoryReviewLogRepository()
    repo.append(_make())
    repo.clear()
    assert repo.count_for_card("schema.x.v1") == 0
