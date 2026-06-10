"""Тесты VectorIndex и KnowledgeBaseVersion (T-S01-004, часть 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from schemas.rag.knowledge_base_version import (
    InvalidKBTransitionError,
    KBStatus,
    KnowledgeBaseVersion,
)
from schemas.rag.vector_index import VectorIndex, VectorIndexStatus

pytestmark = pytest.mark.unit


def _make_index(**overrides: object) -> VectorIndex:
    defaults: dict[str, object] = {
        "index_version": "idx_2026_05_19_v1",
        "embedding_model": "nomic-embed-text",
        "created_at": datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return VectorIndex.model_validate(defaults)


class TestVectorIndex:
    def test_valid_index(self) -> None:
        idx = _make_index()
        assert idx.status == VectorIndexStatus.BUILDING
        assert idx.chunks_count == 0

    def test_counts_consistency(self) -> None:
        # indexed + failed > total — невалидно
        with pytest.raises(ValidationError) as exc:
            _make_index(chunks_count=10, indexed_chunks_count=7, failed_chunks_count=5)
        assert "cannot exceed" in str(exc.value)

    def test_counts_at_boundary_ok(self) -> None:
        idx = _make_index(chunks_count=10, indexed_chunks_count=8, failed_chunks_count=2)
        assert idx.indexed_chunks_count + idx.failed_chunks_count == idx.chunks_count

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_index(chunks_count=-1)


def _make_kb(**overrides: object) -> KnowledgeBaseVersion:
    defaults: dict[str, object] = {
        "knowledge_base_version": "kb_2026_05_19_v1",
        "setup_job_id": "setup_001",
    }
    defaults.update(overrides)
    return KnowledgeBaseVersion.model_validate(defaults)


class TestKnowledgeBaseVersion:
    def test_minimal_valid_kb(self) -> None:
        kb = _make_kb()
        assert kb.status == KBStatus.DRAFT
        assert kb.is_active is False

    def test_all_6_statuses(self) -> None:
        assert {s.value for s in KBStatus} == {
            "draft",
            "testing",
            "ready",
            "active",
            "deprecated",
            "failed",
        }

    def test_is_active_requires_active_status(self) -> None:
        with pytest.raises(ValidationError):
            _make_kb(is_active=True)  # status=DRAFT, не ACTIVE

    def test_active_status_requires_is_active(self) -> None:
        with pytest.raises(ValidationError):
            _make_kb(status=KBStatus.ACTIVE, is_active=False)

    def test_full_lifecycle(self) -> None:
        kb = _make_kb()
        kb.transition_to(KBStatus.TESTING)
        kb.transition_to(KBStatus.READY)
        # Активация требует index_version
        kb.index_version = "idx_001"
        kb.transition_to(KBStatus.ACTIVE)
        assert kb.is_active is True
        assert kb.status == KBStatus.ACTIVE

    def test_activate_without_index_version_fails(self) -> None:
        kb = _make_kb()
        kb.transition_to(KBStatus.TESTING)
        kb.transition_to(KBStatus.READY)
        with pytest.raises(ValueError, match="index_version"):
            kb.transition_to(KBStatus.ACTIVE)

    def test_active_can_only_deprecate(self) -> None:
        kb = _make_kb(index_version="idx_001")
        kb.transition_to(KBStatus.TESTING)
        kb.transition_to(KBStatus.READY)
        kb.transition_to(KBStatus.ACTIVE)

        with pytest.raises(InvalidKBTransitionError):
            kb.transition_to(KBStatus.READY)

        kb.transition_to(KBStatus.DEPRECATED)
        assert kb.is_active is False
        assert kb.status == KBStatus.DEPRECATED

    def test_deprecated_terminal(self) -> None:
        kb = _make_kb(status=KBStatus.DEPRECATED)
        for target in KBStatus:
            with pytest.raises(InvalidKBTransitionError):
                kb.transition_to(target)

    def test_failed_can_restart(self) -> None:
        kb = _make_kb(status=KBStatus.FAILED)
        kb.transition_to(KBStatus.DRAFT)
        assert kb.status == KBStatus.DRAFT
