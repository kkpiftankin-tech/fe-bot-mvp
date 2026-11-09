"""Unit-тесты FragmentClassificationResult (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import pytest
from schemas.classifier.classification_result import (
    ClassifierPathStep,
    FragmentClassificationResult,
)

pytestmark = pytest.mark.unit


def _step(node_id: str, name: str, confidence: float) -> ClassifierPathStep:
    return ClassifierPathStep(node_id=node_id, name=name, confidence=confidence)


class TestFragmentClassificationResult:
    def test_empty_path_has_zero_confidence_and_no_leaf(self) -> None:
        result = FragmentClassificationResult(tree_id="t1", path=[])
        assert result.overall_confidence == 0.0
        assert result.leaf_node_id is None
        assert result.path_names == []

    def test_overall_confidence_is_minimum_across_path(self) -> None:
        result = FragmentClassificationResult(
            tree_id="t1",
            path=[_step("a", "A", 0.95), _step("b", "B", 0.6), _step("c", "C", 0.8)],
        )
        assert result.overall_confidence == 0.6

    def test_leaf_node_id_is_last_step(self) -> None:
        result = FragmentClassificationResult(
            tree_id="t1", path=[_step("a", "A", 0.9), _step("b", "B", 0.9)]
        )
        assert result.leaf_node_id == "b"
        assert result.path_names == ["A", "B"]

    def test_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="less than or equal to 1"):
            ClassifierPathStep(node_id="a", name="A", confidence=1.5)
