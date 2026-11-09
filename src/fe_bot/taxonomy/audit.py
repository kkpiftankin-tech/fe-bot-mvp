"""Taxonomy audit emitters (SETUP-12 / T-S12-102).

Тонкие обёртки над ``AuditService.record`` для taxonomy events:
- auto-create нового класса (TAXONOMY_CLASS_AUTO_CREATED).
- force-merge при overflow (TAXONOMY_CLASS_FORCE_MERGED).
- overflow без similar neighbour (TAXONOMY_CLASS_OVERFLOW).

Все события имеют payload с context'ом: level, parent_path,
similarity, resulting bit_index, triggering section_id.
"""

from __future__ import annotations

import logging

from fe_bot.audit.service import (
    AuditAction,
    AuditOutcome,
    AuditService,
)
from fe_bot.taxonomy.auto_allocator import (
    AllocationResult,
    AllocationSource,
)

logger = logging.getLogger(__name__)


class TaxonomyAuditEmitter:
    """Wraps AuditService для taxonomy-specific event emission."""

    def __init__(
        self,
        audit: AuditService,
        *,
        actor_id: str = "taxonomy_auto_allocator",
    ) -> None:
        self._audit = audit
        self._actor_id = actor_id

    def emit_allocation(
        self,
        result: AllocationResult,
        *,
        triggered_by_section_id: str,
        setup_job_id: str | None = None,
    ) -> None:
        """Emit AuditEvent если allocation вызвал создание / merge.

        Безусловно безопасный для SLUG_MATCH / SIMILARITY_REUSE — это
        normal-path аллокации и не требует audit'а.
        """
        if result.source not in {
            AllocationSource.AUTO_CREATE,
            AllocationSource.FORCE_MERGE,
            AllocationSource.CLASS_OVERFLOW,
        }:
            return

        action = _SOURCE_TO_ACTION[result.source]
        target_type = "taxonomy_class"
        entry = result.target_entry
        target_id = f"{entry.version_id}:{entry.level}:{entry.parent_path or '_root'}:{entry.bit_index}"
        payload = {
            "level": entry.level,
            "parent_path": entry.parent_path,
            "bit_index": entry.bit_index,
            "class_slug": entry.class_slug,
            "source": result.source.value,
            "triggered_by_section_id": triggered_by_section_id,
            "similarity_to_closest": result.similarity_to_closest,
            "closest_existing_slug": result.closest_existing_slug,
            "warning_message": result.warning_message,
        }
        outcome = (
            AuditOutcome.SUCCESS
            if result.source == AllocationSource.AUTO_CREATE
            else AuditOutcome.FAILURE
        )
        try:
            self._audit.record(
                actor_id=self._actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                setup_job_id=setup_job_id,
                outcome=outcome,
                payload=payload,
            )
        except Exception:
            logger.exception(
                "TaxonomyAuditEmitter: failed to record audit event "
                "(allocation result=%s)",
                result.source.value,
            )


_SOURCE_TO_ACTION: dict[AllocationSource, AuditAction] = {
    AllocationSource.AUTO_CREATE: AuditAction.TAXONOMY_CLASS_AUTO_CREATED,
    AllocationSource.FORCE_MERGE: AuditAction.TAXONOMY_CLASS_FORCE_MERGED,
    AllocationSource.CLASS_OVERFLOW: AuditAction.TAXONOMY_CLASS_OVERFLOW,
}


__all__ = ["TaxonomyAuditEmitter"]
