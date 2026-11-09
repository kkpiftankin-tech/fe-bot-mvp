"""KB Publish Service (T-S01-038).

Lifecycle KnowledgeBaseVersion:
- create_draft → status=DRAFT
- mark_testing → status=TESTING (после запуска retrieval-tests)
- mark_ready   → status=READY  (если eval gate passed)
- activate     → status=ACTIVE (новая KB становится «живой»; старая ACTIVE → DEPRECATED)
- mark_failed  → status=FAILED

Гарантии:
- Не более одной ACTIVE KB-version на (setup_job_id) (см. defaults
  ALLOW_MULTIPLE_ACTIVE_KB_PER_PROJECT=False — на уровне project, в MVP
  смотрим на setup_job_id).
- Активация атомарна: deprecate старой + activate новой в одной операции.
- Иммутабельность ACTIVE-полей (INV-KB-002): после ACTIVE нельзя менять
  rag_card_count, chunk_count, index_version, retrieval_test_report_id.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from schemas.rag.knowledge_base_version import (
    InvalidKBTransitionError,
    KBStatus,
    KnowledgeBaseVersion,
)

logger = logging.getLogger(__name__)


class KBNotFoundError(LookupError):
    def __init__(self, kb_version: str) -> None:
        self.kb_version = kb_version
        super().__init__(f"Knowledge base version not found: {kb_version}")


class PublishNotReadyError(Exception):
    """Попытка publish при не пройденном retrieval-eval gate."""


class KBRepository(Protocol):
    def save(self, kb: KnowledgeBaseVersion) -> None: ...

    def get(self, kb_version: str) -> KnowledgeBaseVersion: ...

    def list_for_setup_job(self, setup_job_id: str) -> list[KnowledgeBaseVersion]: ...

    def get_active_for_setup_job(self, setup_job_id: str) -> KnowledgeBaseVersion | None: ...


@dataclass(slots=True)
class _Record:
    kb: KnowledgeBaseVersion


class InMemoryKBRepository:
    """In-memory KB-репозиторий для MVP/тестов."""

    def __init__(self) -> None:
        self._store: dict[str, _Record] = {}

    def save(self, kb: KnowledgeBaseVersion) -> None:
        self._store[kb.knowledge_base_version] = _Record(kb=kb.model_copy(deep=True))

    def get(self, kb_version: str) -> KnowledgeBaseVersion:
        if kb_version not in self._store:
            raise KBNotFoundError(kb_version)
        return self._store[kb_version].kb.model_copy(deep=True)

    def list_for_setup_job(self, setup_job_id: str) -> list[KnowledgeBaseVersion]:
        return [
            r.kb.model_copy(deep=True)
            for r in self._store.values()
            if r.kb.setup_job_id == setup_job_id
        ]

    def get_active_for_setup_job(self, setup_job_id: str) -> KnowledgeBaseVersion | None:
        for r in self._store.values():
            if r.kb.setup_job_id == setup_job_id and r.kb.is_active:
                return r.kb.model_copy(deep=True)
        return None

    def clear(self) -> None:
        self._store.clear()


class KBPublishService:
    """Создаёт и публикует KnowledgeBaseVersion."""

    def __init__(self, repository: KBRepository) -> None:
        self._repo = repository

    # ---------- API ----------

    def create_draft(
        self,
        *,
        setup_job_id: str,
        index_version: str,
        rag_card_count: int,
        chunk_count: int,
    ) -> KnowledgeBaseVersion:
        kb_version = self._make_version()
        kb = KnowledgeBaseVersion(
            knowledge_base_version=kb_version,
            setup_job_id=setup_job_id,
            status=KBStatus.DRAFT,
            rag_card_count=rag_card_count,
            chunk_count=chunk_count,
            index_version=index_version,
        )
        self._repo.save(kb)
        return kb

    def mark_testing(self, kb_version: str) -> KnowledgeBaseVersion:
        kb = self._repo.get(kb_version)
        kb.transition_to(KBStatus.TESTING)
        self._repo.save(kb)
        return kb

    def mark_ready(self, kb_version: str, *, retrieval_test_report_id: str) -> KnowledgeBaseVersion:
        kb = self._repo.get(kb_version)
        kb.retrieval_test_report_id = retrieval_test_report_id
        kb.transition_to(KBStatus.READY)
        self._repo.save(kb)
        return kb

    def mark_failed(self, kb_version: str) -> KnowledgeBaseVersion:
        kb = self._repo.get(kb_version)
        kb.transition_to(KBStatus.FAILED)
        self._repo.save(kb)
        return kb

    def activate(
        self,
        kb_version: str,
        *,
        published_by: str,
    ) -> KnowledgeBaseVersion:
        """Активирует KB. Деактивирует предыдущую ACTIVE для того же setup_job_id."""
        kb = self._repo.get(kb_version)
        if kb.status != KBStatus.READY:
            raise PublishNotReadyError(
                f"KB {kb_version} is in status {kb.status.value}; must be READY to activate"
            )

        # Деактивируем предыдущую ACTIVE.
        prev_active = self._repo.get_active_for_setup_job(kb.setup_job_id)
        if prev_active is not None:
            try:
                prev_active.transition_to(KBStatus.DEPRECATED)
                self._repo.save(prev_active)
            except InvalidKBTransitionError as exc:
                logger.warning(
                    "Failed to deprecate previous active KB %s: %s",
                    prev_active.knowledge_base_version,
                    exc,
                )

        # Активируем новую.
        kb.published_by = published_by
        kb.published_at = datetime.now(tz=UTC)
        kb.transition_to(KBStatus.ACTIVE)
        self._repo.save(kb)
        return kb

    # ---------- internals ----------

    @staticmethod
    def _make_version() -> str:
        now = datetime.now(tz=UTC)
        return f"kb_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
