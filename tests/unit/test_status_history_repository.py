"""Unit-тесты StatusHistoryRepository (T-S03-006)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest
from schemas.setup.source_document import SourceDocumentStatus
from schemas.setup.status_history import (
    ChangedByType,
    SourceStatusHistoryEntry,
)

from fe_bot.setup.source_registry.status_history import (
    InMemoryStatusHistoryRepository,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    history_id: str = "hist_001",
    source_id: str = "src_001",
    event_id: str = "evt_001",
    old: SourceDocumentStatus | None = SourceDocumentStatus.UPLOADED,
    new: SourceDocumentStatus = SourceDocumentStatus.REGISTERED,
) -> SourceStatusHistoryEntry:
    return SourceStatusHistoryEntry(
        status_history_id=history_id,
        source_document_id=source_id,
        old_status=old,
        new_status=new,
        event_id=event_id,
        reason="test",
        changed_by_type=ChangedByType.SERVICE,
        changed_by_id="svc",
        changed_at=datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
    )


class TestAppend:
    def test_append_stores_entry(self) -> None:
        repo = InMemoryStatusHistoryRepository()
        entry = _entry()
        stored = repo.append(entry)
        assert stored.event_id == "evt_001"
        assert repo.list_for_document("src_001") == [stored]

    def test_idempotent_by_event_id(self) -> None:
        """Повторный append с тем же event_id возвращает существующую."""
        repo = InMemoryStatusHistoryRepository()
        first = repo.append(_entry())
        second = repo.append(_entry(history_id="hist_DIFFERENT", event_id="evt_001"))
        assert second.status_history_id == first.status_history_id
        # И не создал дубликат в списке.
        assert len(repo.list_for_document("src_001")) == 1


class TestListAndQueries:
    def test_list_returns_chronological_order(self) -> None:
        repo = InMemoryStatusHistoryRepository()
        repo.append(_entry(history_id="h1", event_id="evt_1"))
        repo.append(
            _entry(
                history_id="h2",
                event_id="evt_2",
                old=SourceDocumentStatus.REGISTERED,
                new=SourceDocumentStatus.PARSING,
            )
        )
        items = repo.list_for_document("src_001")
        assert [i.status_history_id for i in items] == ["h1", "h2"]

    def test_list_empty_for_unknown_document(self) -> None:
        repo = InMemoryStatusHistoryRepository()
        assert repo.list_for_document("unknown") == []

    def test_get_by_event_id(self) -> None:
        repo = InMemoryStatusHistoryRepository()
        repo.append(_entry())
        assert repo.get_by_event_id("evt_001") is not None
        assert repo.get_by_event_id("evt_NOPE") is None

    def test_latest_for_document(self) -> None:
        repo = InMemoryStatusHistoryRepository()
        assert repo.latest_for_document("src_001") is None
        repo.append(_entry(history_id="h1", event_id="evt_1"))
        repo.append(
            _entry(
                history_id="h2",
                event_id="evt_2",
                old=SourceDocumentStatus.REGISTERED,
                new=SourceDocumentStatus.PARSING,
            )
        )
        latest = repo.latest_for_document("src_001")
        assert latest is not None
        assert latest.status_history_id == "h2"


class TestThreadSafety:
    def test_concurrent_appends_no_duplicates(self) -> None:
        """100 параллельных append'ов с уникальными event_id → 100 записей."""
        repo = InMemoryStatusHistoryRepository()
        threads: list[threading.Thread] = []
        for i in range(100):
            t = threading.Thread(
                target=lambda idx=i: repo.append(
                    _entry(history_id=f"h_{idx}", event_id=f"evt_{idx}")
                )
            )
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(repo.list_for_document("src_001")) == 100

    def test_concurrent_appends_same_event_id_dedupe(self) -> None:
        """50 параллельных append'ов с тем же event_id → 1 запись."""
        repo = InMemoryStatusHistoryRepository()
        threads: list[threading.Thread] = []
        for i in range(50):
            t = threading.Thread(
                target=lambda idx=i: repo.append(_entry(history_id=f"h_{idx}", event_id="evt_SAME"))
            )
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(repo.list_for_document("src_001")) == 1
