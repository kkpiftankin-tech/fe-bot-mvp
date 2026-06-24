"""ChunkingOrchestrator (SETUP-08 / T-S08-006).

Координирует batch chunking: собирает eligible карточки, прогоняет
ChunkingService, сохраняет ChunkManifest, переводит status в CHUNKED.

Source of truth — docs/02-system/features/SETUP-08-chunking.md §7.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime

from schemas.rag.chunk import Chunk
from schemas.rag.rag_card import CardStatus
from schemas.setup.chunk_manifest import ChunkingRunDTO, ChunkManifestDTO

from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.setup.card_registry.service import RAGCardRegistry
from fe_bot.setup.chunking.events import (
    ChunkingRunCompletedEvent,
    ChunkingRunStartedEvent,
    _BaseChunkingEvent,
    event_payload,
    event_type_of,
)
from fe_bot.setup.chunking.manifest_repository import (
    InMemoryChunkManifestRepository,
)
from fe_bot.setup.chunking.metrics import ChunkingMetricsCollector
from fe_bot.setup.chunking.service import ChunkingService
from fe_bot.setup.events import EventBus, SetupProgressEvent

logger = logging.getLogger(__name__)


_ELIGIBLE_STATUSES = frozenset(
    {
        CardStatus.METADATA_VALIDATED,
        CardStatus.APPROVED,
    }
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ChunkingOrchestrator:
    """Batch chunking + persistence + events + audit + metrics."""

    def __init__(
        self,
        *,
        registry: RAGCardRegistry,
        chunking: ChunkingService,
        manifest_repo: InMemoryChunkManifestRepository | None = None,
        event_bus: EventBus | None = None,
        audit_service: AuditService | None = None,
        metrics: ChunkingMetricsCollector | None = None,
    ) -> None:
        self._registry = registry
        self._chunking = chunking
        self._manifests = manifest_repo
        self._bus = event_bus
        self._audit = audit_service
        self._metrics = metrics or ChunkingMetricsCollector()

    def run_for_job(
        self,
        setup_job_id: str,
        *,
        triggered_by: str = "system",
    ) -> ChunkingRunDTO:
        run_id = _gen_id("crun")
        manifest_id = _gen_id("manifest")
        started = _now()

        records = self._registry.list_for_job(
            setup_job_id, status_in=_ELIGIBLE_STATUSES
        )

        # Audit + event run_started.
        self._audit_record(
            actor_id=triggered_by,
            action=AuditAction.CHUNKING_RUN_TRIGGERED,
            target_id=run_id,
            setup_job_id=setup_job_id,
            payload={"total_cards": len(records)},
        )
        self._emit(
            ChunkingRunStartedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=setup_job_id,
                occurred_at=started,
                chunking_run_id=run_id,
                triggered_by=triggered_by,
                total_cards=len(records),
            )
        )

        all_chunks: list[Chunk] = []
        by_type: Counter[str] = Counter()
        for rec in records:
            card_start = _now()
            chunks = self._chunking.chunk_card(card=rec.card, metadata=rec.metadata)
            all_chunks.extend(chunks)
            for c in chunks:
                self._metrics.record_chunk(chunk_type=c.chunk_type.value)
                by_type[c.chunk_type.value] += 1

            # Update card status to CHUNKED.
            try:
                if rec.card.can_transition_to(CardStatus.CHUNKED):
                    updated = rec.card.model_copy(update={"status": CardStatus.CHUNKED})
                    self._registry.update(
                        rec.card.doc_id,
                        card=updated,
                        note=f"chunked via run {run_id}",
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "chunking_status_update_failed",
                    extra={"doc_id": rec.card.doc_id, "error": str(exc)},
                )

            duration_ms = max(int((_now() - card_start).total_seconds() * 1000), 0)
            self._metrics.observe_card_duration(duration_ms=duration_ms)

        # Build & save manifest.
        manifest = ChunkManifestDTO(
            manifest_id=manifest_id,
            setup_job_id=setup_job_id,
            chunks=all_chunks,
            total_chunks=len(all_chunks),
            by_type=dict(by_type),
            created_at=_now(),
            created_by=triggered_by,
        )
        if self._manifests is not None:
            self._manifests.save(manifest)

        finished = _now()
        duration_ms = max(int((finished - started).total_seconds() * 1000), 0)

        run = ChunkingRunDTO(
            chunking_run_id=run_id,
            setup_job_id=setup_job_id,
            manifest_id=manifest_id,
            triggered_by=triggered_by,
            total_cards=len(records),
            chunks_created=len(all_chunks),
            duration_ms=duration_ms,
            started_at=started,
            finished_at=finished,
        )
        if self._manifests is not None:
            self._manifests.save_run(run)

        outcome = "completed" if all_chunks else "completed_empty"
        self._metrics.record_run(outcome=outcome)
        self._metrics.observe_run_duration(duration_ms=duration_ms)

        self._audit_record(
            actor_id=triggered_by,
            action=AuditAction.CHUNKING_MANIFEST_CREATED,
            target_id=manifest_id,
            setup_job_id=setup_job_id,
            payload={
                "total_cards": len(records),
                "chunks_created": len(all_chunks),
                "by_type": dict(by_type),
            },
        )
        self._emit(
            ChunkingRunCompletedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=setup_job_id,
                occurred_at=finished,
                chunking_run_id=run_id,
                manifest_id=manifest_id,
                total_cards=len(records),
                chunks_created=len(all_chunks),
                duration_ms=duration_ms,
            )
        )

        logger.info(
            "chunking_run_completed",
            extra={
                "setup_job_id": setup_job_id,
                "chunking_run_id": run_id,
                "manifest_id": manifest_id,
                "total_cards": len(records),
                "chunks_created": len(all_chunks),
                "by_type": dict(by_type),
                "duration_ms": duration_ms,
                "outcome": outcome,
            },
        )

        return run

    def preview_card(self, doc_id: str) -> list[Chunk]:
        """Preview chunks для одной карточки без persistence (T-S08-008)."""
        rec = self._registry.get(doc_id)
        return self._chunking.chunk_card(card=rec.card, metadata=rec.metadata)

    def refresh_card(
        self,
        doc_id: str,
        *,
        triggered_by: str = "system",
    ) -> list[Chunk]:
        """Re-chunk одной карточки и обновляет manifest setup_job (T-S08-009).

        В MVP — replace manifest для одной карточки внутри latest manifest:
        для простоты создаём новый manifest entry для setup_job только с
        chunks этой карточки. Полный merge — в SETUP-09.
        """
        rec = self._registry.get(doc_id)
        chunks = self._chunking.chunk_card(card=rec.card, metadata=rec.metadata)

        if self._manifests is not None:
            manifest_id = _gen_id("manifest")
            manifest = ChunkManifestDTO(
                manifest_id=manifest_id,
                setup_job_id=rec.setup_job_id,
                chunks=chunks,
                total_chunks=len(chunks),
                by_type={c.chunk_type.value: 1 for c in chunks},
                created_at=_now(),
                created_by=triggered_by,
            )
            self._manifests.save(manifest)

        return chunks

    def _emit(self, event: _BaseChunkingEvent) -> None:
        if self._bus is None:
            return
        self._bus.publish(
            SetupProgressEvent(
                event_type=event_type_of(event),
                setup_job_id=event.setup_job_id,
                step=None,
                status="in_progress",
                progress_percent=0.0,
                message=None,
                metrics=event_payload(event),
            )
        )

    def _audit_record(
        self,
        *,
        actor_id: str,
        action: AuditAction,
        target_id: str,
        setup_job_id: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            actor_id=actor_id,
            action=action,
            target_type="chunking_run" if action == AuditAction.CHUNKING_RUN_TRIGGERED else "chunk_manifest",
            target_id=target_id,
            setup_job_id=setup_job_id,
            payload=payload or {},
        )
