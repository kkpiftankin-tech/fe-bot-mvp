"""Unit tests for SETUP-06 CardStatus extension (T-S06-006)."""

from __future__ import annotations

import pytest

from schemas.rag.rag_card import CardStatus, InvalidCardTransitionError, _FORWARD_CARD_TRANSITIONS


def _can(from_status: CardStatus, to_status: CardStatus) -> bool:
    return to_status in _FORWARD_CARD_TRANSITIONS.get(from_status, frozenset())


def test_new_statuses_present():
    for status_value in ("editing", "edited", "regenerate_requested", "validation_failed"):
        assert CardStatus(status_value) is not None


def test_generated_to_review_decisions():
    assert _can(CardStatus.GENERATED, CardStatus.APPROVED)
    assert _can(CardStatus.GENERATED, CardStatus.REJECTED)
    assert _can(CardStatus.GENERATED, CardStatus.EDITED)
    assert _can(CardStatus.GENERATED, CardStatus.EDITING)
    assert _can(CardStatus.GENERATED, CardStatus.REGENERATE_REQUESTED)


def test_review_required_to_all_decisions():
    assert _can(CardStatus.REVIEW_REQUIRED, CardStatus.APPROVED)
    assert _can(CardStatus.REVIEW_REQUIRED, CardStatus.REJECTED)
    assert _can(CardStatus.REVIEW_REQUIRED, CardStatus.EDITED)
    assert _can(CardStatus.REVIEW_REQUIRED, CardStatus.REGENERATE_REQUESTED)


def test_low_confidence_to_decisions():
    assert _can(CardStatus.LOW_CONFIDENCE, CardStatus.APPROVED)
    assert _can(CardStatus.LOW_CONFIDENCE, CardStatus.REJECTED)
    assert _can(CardStatus.LOW_CONFIDENCE, CardStatus.EDITED)
    assert _can(CardStatus.LOW_CONFIDENCE, CardStatus.REGENERATE_REQUESTED)


def test_metadata_incomplete_to_decisions():
    assert _can(CardStatus.METADATA_INCOMPLETE, CardStatus.EDITED)
    assert _can(CardStatus.METADATA_INCOMPLETE, CardStatus.REGENERATE_REQUESTED)
    assert _can(CardStatus.METADATA_INCOMPLETE, CardStatus.REJECTED)


def test_validation_failed_to_decisions():
    assert _can(CardStatus.VALIDATION_FAILED, CardStatus.EDITED)
    assert _can(CardStatus.VALIDATION_FAILED, CardStatus.EDITING)
    assert _can(CardStatus.VALIDATION_FAILED, CardStatus.REGENERATE_REQUESTED)
    assert _can(CardStatus.VALIDATION_FAILED, CardStatus.REJECTED)


def test_editing_to_edited_or_review_required():
    assert _can(CardStatus.EDITING, CardStatus.EDITED)
    assert _can(CardStatus.EDITING, CardStatus.REVIEW_REQUIRED)


def test_edited_to_terminal_decisions():
    assert _can(CardStatus.EDITED, CardStatus.APPROVED)
    assert _can(CardStatus.EDITED, CardStatus.REJECTED)
    assert _can(CardStatus.EDITED, CardStatus.REGENERATE_REQUESTED)
    assert _can(CardStatus.EDITED, CardStatus.READY_FOR_METADATA_VALIDATION)


def test_regenerate_requested_to_new_card_states():
    assert _can(CardStatus.REGENERATE_REQUESTED, CardStatus.GENERATED)
    assert _can(CardStatus.REGENERATE_REQUESTED, CardStatus.GENERATION_FAILED)
    assert _can(CardStatus.REGENERATE_REQUESTED, CardStatus.DEPRECATED)


def test_rejected_remains_terminal():
    # REJECTED — terminal по spec §12.
    assert _FORWARD_CARD_TRANSITIONS[CardStatus.REJECTED] == frozenset()


def test_approved_can_revert_to_review_required():
    # Edit approved карточки разрешён через возврат в review_required (через
    # новую версию) — см. spec §12 "approved → edited только через новую версию".
    assert _can(CardStatus.APPROVED, CardStatus.REVIEW_REQUIRED)


def test_invalid_transition_raises():
    # Reject → approved запрещён напрямую (см. spec §12).
    assert not _can(CardStatus.REJECTED, CardStatus.APPROVED)


def test_all_setup06_statuses_have_transitions_defined():
    for status in (
        CardStatus.EDITING,
        CardStatus.EDITED,
        CardStatus.REGENERATE_REQUESTED,
        CardStatus.VALIDATION_FAILED,
    ):
        assert status in _FORWARD_CARD_TRANSITIONS, (
            f"{status.value} must have outgoing transitions defined"
        )


def test_invalid_card_transition_error_signature():
    err = InvalidCardTransitionError(CardStatus.REJECTED, CardStatus.APPROVED)
    assert err.from_status == CardStatus.REJECTED
    assert err.to_status == CardStatus.APPROVED
    assert "rejected" in str(err) and "approved" in str(err)
