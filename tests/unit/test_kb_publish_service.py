"""Тесты KB Publish Service (T-S01-038)."""

from __future__ import annotations

import pytest
from schemas.rag.knowledge_base_version import (
    InvalidKBTransitionError,
    KBStatus,
)

from fe_bot.setup.publish.service import (
    InMemoryKBRepository,
    KBNotFoundError,
    KBPublishService,
    PublishNotReadyError,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def repo() -> InMemoryKBRepository:
    return InMemoryKBRepository()


@pytest.fixture
def svc(repo: InMemoryKBRepository) -> KBPublishService:
    return KBPublishService(repo)


class TestCreateDraft:
    def test_create_draft_returns_kb_in_draft_status(self, svc: KBPublishService) -> None:
        kb = svc.create_draft(
            setup_job_id="setup_1",
            index_version="idx_1",
            rag_card_count=3,
            chunk_count=9,
        )
        assert kb.status == KBStatus.DRAFT
        assert kb.knowledge_base_version.startswith("kb_")
        assert kb.is_active is False
        assert kb.published_at is None


class TestLifecycle:
    def test_full_happy_path(self, svc: KBPublishService, repo: InMemoryKBRepository) -> None:
        kb = svc.create_draft(
            setup_job_id="setup_1",
            index_version="idx_1",
            rag_card_count=3,
            chunk_count=9,
        )
        kb_v = kb.knowledge_base_version

        svc.mark_testing(kb_v)
        assert repo.get(kb_v).status == KBStatus.TESTING

        svc.mark_ready(kb_v, retrieval_test_report_id="rep_1")
        assert repo.get(kb_v).status == KBStatus.READY
        assert repo.get(kb_v).retrieval_test_report_id == "rep_1"

        active = svc.activate(kb_v, published_by="admin")
        assert active.status == KBStatus.ACTIVE
        assert active.is_active is True
        assert active.published_by == "admin"
        assert active.published_at is not None

    def test_activate_deprecates_previous(
        self, svc: KBPublishService, repo: InMemoryKBRepository
    ) -> None:
        # KB v1 → ACTIVE
        kb1 = svc.create_draft(
            setup_job_id="setup_1",
            index_version="idx_1",
            rag_card_count=3,
            chunk_count=9,
        )
        svc.mark_testing(kb1.knowledge_base_version)
        svc.mark_ready(kb1.knowledge_base_version, retrieval_test_report_id="r1")
        svc.activate(kb1.knowledge_base_version, published_by="admin")

        # KB v2 → ACTIVE → v1 deprecated
        kb2 = svc.create_draft(
            setup_job_id="setup_1",
            index_version="idx_2",
            rag_card_count=4,
            chunk_count=12,
        )
        svc.mark_testing(kb2.knowledge_base_version)
        svc.mark_ready(kb2.knowledge_base_version, retrieval_test_report_id="r2")
        svc.activate(kb2.knowledge_base_version, published_by="admin")

        v1_after = repo.get(kb1.knowledge_base_version)
        assert v1_after.status == KBStatus.DEPRECATED
        assert v1_after.is_active is False

        active = repo.get_active_for_setup_job("setup_1")
        assert active is not None
        assert active.knowledge_base_version == kb2.knowledge_base_version


class TestErrors:
    def test_activate_non_ready_raises(self, svc: KBPublishService) -> None:
        kb = svc.create_draft(
            setup_job_id="s", index_version="idx", rag_card_count=1, chunk_count=1
        )
        with pytest.raises(PublishNotReadyError):
            svc.activate(kb.knowledge_base_version, published_by="admin")

    def test_mark_ready_from_draft_invalid_transition(self, svc: KBPublishService) -> None:
        kb = svc.create_draft(
            setup_job_id="s", index_version="idx", rag_card_count=1, chunk_count=1
        )
        # DRAFT → READY запрещён (нужно TESTING).
        with pytest.raises(InvalidKBTransitionError):
            svc.mark_ready(kb.knowledge_base_version, retrieval_test_report_id="r")

    def test_unknown_kb_raises(self, svc: KBPublishService) -> None:
        with pytest.raises(KBNotFoundError):
            svc.mark_testing("nope")

    def test_mark_failed_from_testing(self, svc: KBPublishService) -> None:
        kb = svc.create_draft(
            setup_job_id="s", index_version="idx", rag_card_count=1, chunk_count=1
        )
        svc.mark_testing(kb.knowledge_base_version)
        kb_after = svc.mark_failed(kb.knowledge_base_version)
        assert kb_after.status == KBStatus.FAILED


class TestQueries:
    def test_list_for_setup_job_returns_multiple(
        self, svc: KBPublishService, repo: InMemoryKBRepository
    ) -> None:
        svc.create_draft(setup_job_id="s1", index_version="i", rag_card_count=1, chunk_count=1)
        svc.create_draft(setup_job_id="s1", index_version="i", rag_card_count=1, chunk_count=1)
        svc.create_draft(setup_job_id="s2", index_version="i", rag_card_count=1, chunk_count=1)
        assert len(repo.list_for_setup_job("s1")) == 2
        assert len(repo.list_for_setup_job("s2")) == 1

    def test_get_active_for_setup_job_no_active(
        self, svc: KBPublishService, repo: InMemoryKBRepository
    ) -> None:
        svc.create_draft(setup_job_id="s1", index_version="i", rag_card_count=1, chunk_count=1)
        assert repo.get_active_for_setup_job("s1") is None
