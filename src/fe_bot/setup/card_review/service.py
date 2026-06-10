"""RAG Card Review Service (T-S01-025).

4 действия (см. SETUP-01 §7.2 A2):
- approve: review_required → approved
- reject: review_required → deprecated
- edit: создаёт новую версию карточки (vN+1), старая → deprecated
- regenerate: возвращает карточку в draft (для следующего прогона генератора)

Каждое действие создаёт RAGCardReviewDTO-like запись в history карточки
и пишет AuditEventDTO (TODO[S8]: реальная связка с Audit Service).
"""

from __future__ import annotations

import contextlib
import re
from datetime import UTC, datetime
from enum import StrEnum

from schemas.rag.rag_card import CardStatus, InvalidCardTransitionError

from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    CardRecord,
    RAGCardRegistry,
)


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    REGENERATE = "regenerate"


class ReviewError(Exception):
    """Базовый класс для review-ошибок."""


class InvalidReviewStateError(ReviewError):
    """Карточка не в состоянии, разрешающем review."""

    def __init__(self, doc_id: str, status: CardStatus) -> None:
        self.doc_id = doc_id
        self.status = status
        super().__init__(
            f"Card {doc_id!r} is in status {status.value!r}; cannot review"
        )


class InvalidEditPayloadError(ReviewError):
    """edit без полезного payload."""


# Статусы, в которых карточка готова к review.
_REVIEWABLE = frozenset(
    {CardStatus.REVIEW_REQUIRED, CardStatus.METADATA_VALIDATED, CardStatus.GENERATED}
)


_VERSION_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?$")


def _bump_version(version: str) -> str:
    """1.0 → 1.1, 1.2 → 1.3, 2.0.1 → 2.0.2."""
    match = _VERSION_RE.match(version)
    if match is None:
        return f"{version}.1"
    major, minor, patch = match.groups()
    if patch is not None:
        return f"{major}.{minor}.{int(patch) + 1}"
    if minor is not None:
        return f"{major}.{int(minor) + 1}"
    return f"{int(major) + 1}"


def _new_doc_id(old_doc_id: str, new_version: str) -> str:
    """`<base>.v1` → `<base>.v1.1`, либо просто заменяем суффикс vN на v{new}."""
    # Соглашение генератора: `<doc_type>.<slug>.v1`. Заменяем хвост.
    parts = old_doc_id.rsplit(".v", 1)
    if len(parts) == 2:
        return f"{parts[0]}.v{new_version}"
    return f"{old_doc_id}.{new_version}"


class RAGCardReviewService:
    """Управляет HITL-решениями по RAG-карточкам."""

    def __init__(self, registry: RAGCardRegistry) -> None:
        self._registry = registry

    # ----------- API -----------

    def approve(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        comment: str | None = None,
    ) -> CardRecord:
        rec = self._load_reviewable(doc_id)
        card = rec.card
        target = CardStatus.APPROVED
        if not card.can_transition_to(target):
            # Если карточка GENERATED или METADATA_VALIDATED, валидный путь —
            # через REVIEW_REQUIRED. Промежуточно переведём.
            with contextlib.suppress(InvalidCardTransitionError):
                card = card.model_copy(
                    update={"status": CardStatus.REVIEW_REQUIRED}
                )
        updated_card = card.model_copy(
            update={
                "status": target,
                "reviewed_by": reviewer_id,
            }
        )
        note = self._format_note("approve", reviewer_id, comment)
        return self._registry.update(doc_id, card=updated_card, note=note)

    def reject(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        comment: str | None = None,
    ) -> CardRecord:
        rec = self._load_reviewable(doc_id)
        target = CardStatus.DEPRECATED
        if not rec.card.can_transition_to(target):
            raise InvalidReviewStateError(doc_id, rec.card.status)
        updated_card = rec.card.model_copy(
            update={
                "status": target,
                "reviewed_by": reviewer_id,
            }
        )
        note = self._format_note("reject", reviewer_id, comment)
        return self._registry.update(doc_id, card=updated_card, note=note)

    def edit(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        updated_body_markdown: str | None = None,
        updated_title: str | None = None,
        comment: str | None = None,
    ) -> CardRecord:
        """Создаёт новую версию карточки с правками, старая → DEPRECATED.

        В MVP edit умеет менять только title и body_markdown. Изменение
        metadata (domain, phase и пр.) — отдельный flow в S5+.
        """
        if updated_body_markdown is None and updated_title is None:
            raise InvalidEditPayloadError(
                "edit must provide updated_title and/or updated_body_markdown"
            )
        rec = self._load_reviewable(doc_id)
        old_card = rec.card

        new_version = _bump_version(old_card.version)
        new_id = _new_doc_id(old_card.doc_id, new_version)
        if self._registry.exists(new_id):
            # маловероятно, но защищаемся от коллизий
            raise InvalidEditPayloadError(
                f"Edited version doc_id {new_id!r} already exists"
            )

        now = datetime.now(tz=UTC)
        new_card = old_card.model_copy(
            update={
                "doc_id": new_id,
                "version": new_version,
                "status": CardStatus.APPROVED,
                "title": updated_title if updated_title is not None else old_card.title,
                "body_markdown": (
                    updated_body_markdown
                    if updated_body_markdown is not None
                    else old_card.body_markdown
                ),
                "reviewed_by": reviewer_id,
                "front_matter": {
                    **old_card.front_matter,
                    "doc_id": new_id,
                    "version": new_version,
                    "supersedes": old_card.doc_id,
                },
                "created_at": now,
                "updated_at": now,
            }
        )
        new_metadata = rec.metadata.model_copy(update={"doc_id": new_id})
        # Регистрируем новую версию карточки.
        new_record = self._registry.add(
            setup_job_id=rec.setup_job_id,
            card=new_card,
            metadata=new_metadata,
            section_id=rec.section_id,
        )
        # Старая → DEPRECATED.
        deprecated = old_card.model_copy(
            update={
                "status": CardStatus.DEPRECATED,
                "reviewed_by": reviewer_id,
            }
        )
        note = self._format_note(
            "edit",
            reviewer_id,
            f"superseded by {new_id}" + (f" — {comment}" if comment else ""),
        )
        self._registry.update(doc_id, card=deprecated, note=note)
        return new_record

    def regenerate(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        comment: str | None = None,
    ) -> CardRecord:
        """Помечает карточку как требующую перегенерации (status=DRAFT)."""
        rec = self._load_reviewable(doc_id)
        target = CardStatus.DRAFT
        if not rec.card.can_transition_to(target):
            # REVIEW_REQUIRED → DRAFT — валидный по lifecycle.
            raise InvalidReviewStateError(doc_id, rec.card.status)
        updated_card = rec.card.model_copy(
            update={
                "status": target,
                "reviewed_by": reviewer_id,
            }
        )
        note = self._format_note("regenerate", reviewer_id, comment)
        return self._registry.update(doc_id, card=updated_card, note=note)

    # ----------- internals -----------

    def _load_reviewable(self, doc_id: str) -> CardRecord:
        try:
            rec = self._registry.get(doc_id)
        except CardNotFoundError:
            raise
        if rec.card.status not in _REVIEWABLE:
            raise InvalidReviewStateError(doc_id, rec.card.status)
        return rec

    @staticmethod
    def _format_note(
        action: str, reviewer_id: str, comment: str | None
    ) -> str:
        base = f"{action} by {reviewer_id}"
        return f"{base}: {comment}" if comment else base
