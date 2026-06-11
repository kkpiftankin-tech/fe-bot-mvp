"""Unit-тесты Status History DTO + state machine (T-S03-002)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.setup.source_document import SourceDocumentStatus
from schemas.setup.status_history import (
    ALLOWED_TRANSITIONS,
    ChangedByType,
    InvalidStatusTransitionError,
    SourceStatusHistoryEntry,
    ensure_valid_transition,
    validate_transition,
)

pytestmark = pytest.mark.unit


def _make_entry(**overrides: object) -> SourceStatusHistoryEntry:
    defaults: dict[str, object] = {
        "status_history_id": "hist_001",
        "source_document_id": "src_001",
        "old_status": SourceDocumentStatus.UPLOADED,
        "new_status": SourceDocumentStatus.REGISTERED,
        "event_id": "evt_001",
        "reason": "Document registered",
        "changed_by_type": ChangedByType.SERVICE,
        "changed_by_id": "document-upload-service",
        "changed_at": datetime(2026, 6, 10, 10, 0, tzinfo=UTC),
        "metadata": {},
    }
    defaults.update(overrides)
    return SourceStatusHistoryEntry(**defaults)  # type: ignore[arg-type]


class TestSourceStatusHistoryEntry:
    def test_valid_minimal(self) -> None:
        entry = _make_entry()
        assert entry.event_id == "evt_001"
        assert entry.old_status == SourceDocumentStatus.UPLOADED
        assert entry.new_status == SourceDocumentStatus.REGISTERED

    def test_initial_state_has_none_old_status(self) -> None:
        entry = _make_entry(old_status=None, new_status=SourceDocumentStatus.UPLOADED)
        assert entry.old_status is None

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            _make_entry(extra_field="x")

    def test_frozen_after_creation(self) -> None:
        entry = _make_entry()
        with pytest.raises(ValidationError):
            entry.new_status = SourceDocumentStatus.PARSING  # type: ignore[misc]

    def test_event_id_max_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_entry(event_id="x" * 129)

    def test_reason_max_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_entry(reason="x" * 2001)


class TestStateMachine:
    """T-S03-002: state machine допустимых переходов (§12 спека)."""

    @pytest.mark.parametrize(
        "old,new",
        [
            (None, SourceDocumentStatus.UPLOADED),
            (None, SourceDocumentStatus.REGISTERED),
            (SourceDocumentStatus.UPLOADED, SourceDocumentStatus.REGISTERED),
            (SourceDocumentStatus.REGISTERED, SourceDocumentStatus.PARSING),
            (SourceDocumentStatus.PARSING, SourceDocumentStatus.PARSED),
            (SourceDocumentStatus.PARSED, SourceDocumentStatus.RAG_CARDS_GENERATING),
            (
                SourceDocumentStatus.RAG_CARDS_GENERATING,
                SourceDocumentStatus.RAG_CARDS_GENERATED,
            ),
            (
                SourceDocumentStatus.RAG_CARDS_GENERATED,
                SourceDocumentStatus.READY_FOR_INDEXING,
            ),
            (SourceDocumentStatus.READY_FOR_INDEXING, SourceDocumentStatus.PUBLISHED),
            (SourceDocumentStatus.PUBLISHED, SourceDocumentStatus.DEPRECATED),
            # retry flow:
            (SourceDocumentStatus.PARSE_FAILED, SourceDocumentStatus.WAITING_FOR_PARSING),
            (SourceDocumentStatus.PROCESSING_FAILED, SourceDocumentStatus.PARSING),
        ],
    )
    def test_allowed_transitions(
        self,
        old: SourceDocumentStatus | None,
        new: SourceDocumentStatus,
    ) -> None:
        assert validate_transition(old, new) is True

    @pytest.mark.parametrize(
        "old,new",
        [
            # Нельзя из removed восстановить.
            (SourceDocumentStatus.REMOVED, SourceDocumentStatus.PARSING),
            (SourceDocumentStatus.REMOVED, SourceDocumentStatus.UPLOADED),
            # Нельзя из uploaded прыгнуть в published без промежуточных шагов.
            (SourceDocumentStatus.UPLOADED, SourceDocumentStatus.PUBLISHED),
            # Нельзя из registered прямо в parsed (нужно пройти parsing).
            (SourceDocumentStatus.REGISTERED, SourceDocumentStatus.PARSED),
            # DEPRECATED — terminal.
            (SourceDocumentStatus.DEPRECATED, SourceDocumentStatus.PUBLISHED),
            # Из processing_failed нельзя сразу в published.
            (SourceDocumentStatus.PROCESSING_FAILED, SourceDocumentStatus.PUBLISHED),
            # Из failed_validation только в removed.
            (SourceDocumentStatus.FAILED_VALIDATION, SourceDocumentStatus.PARSING),
        ],
    )
    def test_forbidden_transitions(
        self,
        old: SourceDocumentStatus,
        new: SourceDocumentStatus,
    ) -> None:
        assert validate_transition(old, new) is False

    def test_same_status_is_idempotent(self) -> None:
        """Переход в тот же статус разрешён (для retry-safe)."""
        for status in SourceDocumentStatus:
            assert validate_transition(status, status) is True

    def test_ensure_valid_transition_raises(self) -> None:
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            ensure_valid_transition(
                source_document_id="src_x",
                old_status=SourceDocumentStatus.REMOVED,
                new_status=SourceDocumentStatus.PARSING,
            )
        assert exc_info.value.source_document_id == "src_x"
        assert exc_info.value.old_status == SourceDocumentStatus.REMOVED

    def test_ensure_valid_transition_passes_for_valid(self) -> None:
        ensure_valid_transition(
            source_document_id="src_x",
            old_status=SourceDocumentStatus.UPLOADED,
            new_status=SourceDocumentStatus.REGISTERED,
        )

    def test_terminal_statuses_have_no_outgoing(self) -> None:
        """DEPRECATED и REMOVED — terminal."""
        assert ALLOWED_TRANSITIONS[SourceDocumentStatus.REMOVED] == set()
        assert ALLOWED_TRANSITIONS[SourceDocumentStatus.DEPRECATED] == set()

    def test_all_statuses_have_transition_rules(self) -> None:
        """Каждый статус (кроме UPLOADED как initial) должен быть в ALLOWED_TRANSITIONS."""
        # UPLOADED тоже есть — initial state.
        for status in SourceDocumentStatus:
            assert status in ALLOWED_TRANSITIONS, (
                f"Status {status} missing in ALLOWED_TRANSITIONS"
            )
