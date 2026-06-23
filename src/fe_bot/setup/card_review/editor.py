"""CardEditorService (SETUP-06 / T-S06-015).

Применяет правки metadata/body к RAG-карточке, валидирует editable fields,
строит diff между версиями.

Editable metadata fields определены явным allowlist'ом — system metadata
(doc_id, version, source_files, created_*, published_*) read-only.

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §10.1, §11.1.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

from schemas.rag.rag_card import RAGCard
from schemas.setup.rag_card_diff import BodyDiff, MetadataFieldDiff, RAGCardDiffDTO


# Editable metadata fields (см. spec §10.1 RAGCardMetadataEditor).
EDITABLE_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "retrieval_tags",
        "domain",
        "task_type",
        "data_source",
        "entity_type",
        "phase",
        "agent_targets",
        "required_input_fields",
        "output_fields",
        "feature_tables",
        "validation_rules",
        "compatible_models",
    }
)

# System metadata — readonly для обычного edit.
SYSTEM_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "doc_id",
        "version",
        "card_version",
        "source_files",
        "source_sections",
        "source_document_ids",
        "source_section_ids",
        "created_by",
        "created_at",
        "published_at",
        "setup_job_id",
        "markdown_artifact_id",
        "primary_source_section_id",
        "created_by_type",
        "created_by_id",
    }
)


class SystemMetadataReadOnlyError(ValueError):
    def __init__(self, fields: list[str]) -> None:
        self.fields = fields
        super().__init__(
            f"Cannot edit system metadata fields: {sorted(fields)}"
        )


class EmptyEditPayloadError(ValueError):
    """Edit без metadata_patch и body_markdown."""


@dataclass(frozen=True)
class EditedCardDraft:
    """Результат apply_patch — новая карточка-черновик."""

    card: RAGCard
    metadata_changed: bool
    body_changed: bool


class CardEditorService:
    """Сервис применения правок к карточке."""

    def apply_patch(
        self,
        card: RAGCard,
        *,
        metadata_patch: dict[str, Any] | None = None,
        body_markdown: str | None = None,
    ) -> EditedCardDraft:
        """Применяет patch и возвращает новую карточку-черновик.

        Не меняет переданный card (immutable update).
        """
        if not metadata_patch and body_markdown is None:
            raise EmptyEditPayloadError("metadata_patch и body_markdown оба пусты")

        # Проверка system metadata
        if metadata_patch:
            blocked = sorted(set(metadata_patch.keys()) & SYSTEM_METADATA_FIELDS)
            if blocked:
                raise SystemMetadataReadOnlyError(blocked)

        update: dict[str, Any] = {}
        metadata_changed = False
        body_changed = False

        # Body update
        if body_markdown is not None and body_markdown != card.body_markdown:
            update["body_markdown"] = body_markdown
            body_changed = True

        # Metadata fields update
        if metadata_patch:
            new_front_matter = dict(card.front_matter)
            for field, value in metadata_patch.items():
                if field not in EDITABLE_METADATA_FIELDS:
                    # игнорируем неизвестные поля (forward compat)
                    continue
                if field == "title":
                    if value != card.title:
                        update["title"] = value
                        metadata_changed = True
                else:
                    if new_front_matter.get(field) != value:
                        new_front_matter[field] = value
                        metadata_changed = True
            if metadata_changed:
                update["front_matter"] = new_front_matter

        if not metadata_changed and not body_changed:
            raise EmptyEditPayloadError("Нет фактических изменений в patch")

        return EditedCardDraft(
            card=card.model_copy(update=update),
            metadata_changed=metadata_changed,
            body_changed=body_changed,
        )

    def calculate_diff(
        self,
        *,
        old_card: RAGCard,
        new_card: RAGCard,
        from_version: str,
        to_version: str,
    ) -> RAGCardDiffDTO:
        """Строит RAGCardDiffDTO по двум версиям карточки."""
        metadata_diff = self._metadata_diff(old_card, new_card)
        body_diff = self._body_diff(old_card.body_markdown, new_card.body_markdown)
        return RAGCardDiffDTO(
            doc_id=new_card.doc_id,
            from_version=from_version,
            to_version=to_version,
            metadata_diff=metadata_diff,
            body_diff=body_diff,
        )

    def _metadata_diff(self, old: RAGCard, new: RAGCard) -> list[MetadataFieldDiff]:
        diffs: list[MetadataFieldDiff] = []
        if old.title != new.title:
            diffs.append(
                MetadataFieldDiff(field="title", old_value=old.title, new_value=new.title)
            )
        old_fm = old.front_matter or {}
        new_fm = new.front_matter or {}
        all_fields = set(old_fm) | set(new_fm)
        for field in sorted(all_fields):
            if field not in EDITABLE_METADATA_FIELDS:
                continue
            if old_fm.get(field) != new_fm.get(field):
                diffs.append(
                    MetadataFieldDiff(
                        field=field,
                        old_value=old_fm.get(field),
                        new_value=new_fm.get(field),
                    )
                )
        return diffs

    def _body_diff(self, old_body: str, new_body: str) -> BodyDiff | None:
        if old_body == new_body:
            return None
        diff_lines = difflib.unified_diff(
            old_body.splitlines(keepends=False),
            new_body.splitlines(keepends=False),
            fromfile="old",
            tofile="new",
            lineterm="",
        )
        content = "\n".join(diff_lines)
        return BodyDiff(content=content)
