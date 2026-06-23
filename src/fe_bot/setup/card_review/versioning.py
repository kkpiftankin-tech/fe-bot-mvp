"""VersioningService (SETUP-06 / T-S06-016).

Создаёт новые версии RAG-карточки. Edit → minor bump (1.0→1.1).
Regenerate → major bump (1.0→2.0).

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §15.3.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.setup.rag_card_version import RAGCardVersionDTO, bump_version


BumpType = Literal["minor", "major"]


@dataclass(frozen=True)
class VersionCreationResult:
    new_card: RAGCard
    version_dto: RAGCardVersionDTO


def _body_hash(body: str) -> str:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _gen_id() -> str:
    return f"art_{uuid.uuid4().hex[:12]}"


class VersioningService:
    """Создаёт новые версии карточки."""

    def create_new_version(
        self,
        old_card: RAGCard,
        *,
        bump_type: BumpType,
        change_reason: str | None,
        created_by: str,
        new_card_body: str | None = None,
        new_card_title: str | None = None,
        new_front_matter: dict[str, object] | None = None,
        markdown_artifact_id: str | None = None,
        target_status: CardStatus = CardStatus.EDITED,
    ) -> VersionCreationResult:
        """Создаёт новую версию карточки.

        ``bump_type``:
        - ``"minor"`` — manual edit (1.0 → 1.1);
        - ``"major"`` — regenerate (1.0 → 2.0).
        """
        old_version = old_card.card_version or old_card.version or "1.0"
        new_version = bump_version(old_version, bump_type=bump_type)

        body = new_card_body if new_card_body is not None else old_card.body_markdown
        title = new_card_title if new_card_title is not None else old_card.title
        front_matter = (
            new_front_matter
            if new_front_matter is not None
            else dict(old_card.front_matter)
        )
        artifact_id = markdown_artifact_id or _gen_id()

        new_card = old_card.model_copy(
            update={
                "version": new_version,
                "card_version": new_version,
                "title": title,
                "body_markdown": body,
                "front_matter": front_matter,
                "status": target_status,
                "markdown_artifact_id": artifact_id,
                "updated_at": _now(),
            }
        )

        version_dto = RAGCardVersionDTO(
            doc_id=old_card.doc_id,
            card_version=new_version,
            parent_card_version=old_version,
            status=target_status,
            markdown_artifact_id=artifact_id,
            metadata_snapshot=front_matter,
            body_hash=_body_hash(body or ""),
            created_by=created_by,
            created_at=_now(),
            change_reason=change_reason,
            is_current=True,
        )

        return VersionCreationResult(new_card=new_card, version_dto=version_dto)
