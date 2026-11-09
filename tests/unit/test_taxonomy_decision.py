"""Unit-тесты schemas.taxonomy.decision (SETUP-12 / T-S12-001)."""

from __future__ import annotations

import pytest
from schemas.taxonomy.decision import (
    Decision,
    DecisionKind,
    ExistingSelection,
    NewClassProposal,
)

pytestmark = pytest.mark.unit


def _proposal(**overrides: object) -> NewClassProposal:
    defaults: dict[str, object] = {
        "name_slug": "new-class",
        "display_name_ru": "Новый класс",
        "display_name_en": "New class",
        "description": "Описание нового класса с достаточной длиной.",
    }
    defaults.update(overrides)
    return NewClassProposal(**defaults)  # type: ignore[arg-type]


class TestExistingSelection:
    def test_valid_selection(self) -> None:
        sel = ExistingSelection(bit=3, confidence=0.85, reason="match")
        assert sel.bit == 3

    def test_bit_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError):
            ExistingSelection(bit=10, confidence=0.5)
        with pytest.raises(ValueError):
            ExistingSelection(bit=-1, confidence=0.5)

    def test_confidence_in_range(self) -> None:
        with pytest.raises(ValueError):
            ExistingSelection(bit=0, confidence=1.5)
        with pytest.raises(ValueError):
            ExistingSelection(bit=0, confidence=-0.1)


class TestNewClassProposal:
    def test_valid_proposal(self) -> None:
        _proposal()

    def test_invalid_slug(self) -> None:
        with pytest.raises(ValueError):
            _proposal(name_slug="UPPER")
        with pytest.raises(ValueError):
            _proposal(name_slug="-leading-dash")

    def test_short_description_rejected(self) -> None:
        with pytest.raises(ValueError):
            _proposal(description="short")  # < 10 chars

    def test_long_description_rejected(self) -> None:
        with pytest.raises(ValueError):
            _proposal(description="x" * 1100)


class TestDecisionInvariants:
    def test_existing_requires_selected(self) -> None:
        with pytest.raises(ValueError, match="EXISTING requires"):
            Decision(
                kind=DecisionKind.EXISTING,
                selected=[],
                overall_confidence=0.8,
            )

    def test_existing_forbids_proposal(self) -> None:
        with pytest.raises(ValueError, match="EXISTING must not"):
            Decision(
                kind=DecisionKind.EXISTING,
                selected=[ExistingSelection(bit=0, confidence=0.8)],
                proposal=_proposal(),
                overall_confidence=0.8,
            )

    def test_existing_ok(self) -> None:
        d = Decision(
            kind=DecisionKind.EXISTING,
            selected=[
                ExistingSelection(bit=0, confidence=0.9),
                ExistingSelection(bit=3, confidence=0.7),
            ],
            overall_confidence=0.85,
            reason="two classes apply",
        )
        assert d.kind == DecisionKind.EXISTING
        assert len(d.selected) == 2

    def test_new_requires_proposal(self) -> None:
        with pytest.raises(ValueError, match="NEW requires"):
            Decision(
                kind=DecisionKind.NEW,
                overall_confidence=0.8,
            )

    def test_new_forbids_selected(self) -> None:
        with pytest.raises(ValueError, match="NEW must not"):
            Decision(
                kind=DecisionKind.NEW,
                selected=[ExistingSelection(bit=0, confidence=0.8)],
                proposal=_proposal(),
                overall_confidence=0.8,
            )

    def test_new_ok(self) -> None:
        d = Decision(
            kind=DecisionKind.NEW,
            proposal=_proposal(),
            overall_confidence=0.75,
        )
        assert d.kind == DecisionKind.NEW
        assert d.proposal is not None
        assert d.proposal.name_slug == "new-class"

    def test_unknown_requires_reason(self) -> None:
        with pytest.raises(ValueError, match="UNKNOWN must include a reason"):
            Decision(
                kind=DecisionKind.UNKNOWN,
                overall_confidence=0.1,
            )

    def test_unknown_forbids_selected(self) -> None:
        with pytest.raises(ValueError, match="UNKNOWN must not"):
            Decision(
                kind=DecisionKind.UNKNOWN,
                selected=[ExistingSelection(bit=0, confidence=0.5)],
                reason="x",
                overall_confidence=0.1,
            )

    def test_unknown_ok(self) -> None:
        d = Decision(
            kind=DecisionKind.UNKNOWN,
            reason="text too generic for classification",
            overall_confidence=0.05,
        )
        assert d.kind == DecisionKind.UNKNOWN

    def test_unique_bits_required(self) -> None:
        with pytest.raises(ValueError, match="Duplicate bit"):
            Decision(
                kind=DecisionKind.EXISTING,
                selected=[
                    ExistingSelection(bit=3, confidence=0.8),
                    ExistingSelection(bit=3, confidence=0.7),
                ],
                overall_confidence=0.75,
            )
