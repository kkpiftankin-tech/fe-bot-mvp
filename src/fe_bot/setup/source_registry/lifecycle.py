"""SourceLifecycleService (SETUP-03 / T-S03-009/010/011).

Высокоуровневый фасад над четырьмя репозиториями:
- SourceRegistry (документы)
- StatusHistoryRepository (история смены статусов)
- ProcessingLogRepository (журнал обработки)
- LineageRepository (связи с derived artifacts)

Предоставляет downstream-сервисам и роутерам единую API-точку:
- update_status: атомарная смена статуса + запись в history.
- append_processing_log: idempotent через event_id.
- link_artifact: idempotent создание lineage relation.
- get_lineage: agregated relations + counters.
- update_user_metadata: PATCH с защитой protected fields.

Все операции — idempotent по event_id, атомарны на уровне репозиториев,
с deep-copy на чтение (SourceRegistry уже это делает).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from schemas.setup.lineage import (
    LineageRelationType,
    LineageTargetType,
    SourceLineageRelation,
)
from schemas.setup.processing_log import (
    ProcessingLogLevel,
    ProcessingLogStep,
    SourceProcessingLogEntry,
)
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus
from schemas.setup.source_document_metadata import (
    SourceDocumentUserMetadata,
    SystemMetadataReadOnlyError,
    UpdateSourceMetadataRequest,
    reject_protected_fields,
)
from schemas.setup.status_history import (
    ChangedByType,
    InvalidStatusTransitionError,
    SourceStatusHistoryEntry,
    ensure_valid_transition,
)

from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.source_registry.lineage import LineageRepository
from fe_bot.setup.source_registry.processing_log import ProcessingLogRepository
from fe_bot.setup.source_registry.service import (
    SourceDocumentNotFoundError,
    SourceRegistry,
)
from fe_bot.setup.source_registry.status_history import StatusHistoryRepository


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


class SourceLifecycleService:
    """Фасад над репозиториями source registry."""

    def __init__(
        self,
        *,
        registry: SourceRegistry,
        status_history: StatusHistoryRepository,
        processing_log: ProcessingLogRepository,
        lineage: LineageRepository,
        event_bus: EventBus | None = None,
        audit_service: AuditService | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self._registry = registry
        self._history = status_history
        self._log = processing_log
        self._lineage = lineage
        # T-S03-020: source.document.* events publication.
        self._bus = event_bus
        # T-S03-022: audit + metrics hooks.
        self._audit = audit_service
        self._metrics = metrics

    def _inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        if self._metrics is not None:
            self._metrics.inc(name, labels=labels, help_text=help_text)

    def _audit_record(
        self,
        *,
        actor_id: str,
        action: AuditAction,
        target_type: str,
        target_id: str,
        setup_job_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._audit is not None:
            self._audit.record(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                setup_job_id=setup_job_id,
                payload=payload or {},
            )

    def _publish(
        self,
        *,
        event_type: str,
        setup_job_id: str,
        message: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Publishes SetupProgressEvent with discriminator event_type.

        SetupProgressEvent (DTO-49) уже обслуживает SSE и аналитику. Источники
        SETUP-03 публикуются через тот же канал с уникальными `event_type` —
        SSE consumer'ы могут фильтровать по prefix `source.document.`.
        """
        if self._bus is None:
            return
        self._bus.publish(
            SetupProgressEvent(
                event_type=event_type,
                setup_job_id=setup_job_id,
                step=None,
                status="in_progress",
                progress_percent=0.0,
                message=message,
                metrics=metrics or {},
            )
        )

    # ============================================================
    # T-S03-009: update_status
    # ============================================================

    def update_status(
        self,
        *,
        source_document_id: str,
        new_status: SourceDocumentStatus,
        event_id: str,
        reason: str | None = None,
        changed_by_type: ChangedByType = ChangedByType.SERVICE,
        changed_by_id: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> SourceDocument:
        """Атомарно меняет status документа и пишет history entry.

        Семантика:
        1. Если event_id уже в history — возвращаем текущий документ (idempotent).
        2. Иначе валидируем transition (old → new) по state machine.
        3. Сначала пишем history entry (append-only, идемпотентно).
        4. Затем обновляем document.status в registry.

        Атомарность: если history append прошёл, но registry.update упал,
        у нас рассинхронизация — но history безопасна (append-only), и
        следующий update_status поймёт по latest history что переход уже был.

        Raises:
            SourceDocumentNotFoundError: документ не найден.
            InvalidStatusTransitionError: недопустимый переход (§12 спека).
        """
        # 1. Idempotency check.
        existing_event = self._history.get_by_event_id(event_id)
        if existing_event is not None:
            return self._registry.get(source_document_id)

        # 2. Load current.
        document = self._registry.get(source_document_id)
        old_status = document.status

        # 3. Validate transition.
        ensure_valid_transition(
            source_document_id=source_document_id,
            old_status=old_status,
            new_status=new_status,
        )

        # 4. Same-status — no-op, но history запишем для audit.
        # (validate_transition разрешает X→X для idempotency.)

        # 5. Append history first.
        entry = SourceStatusHistoryEntry(
            status_history_id=_gen_id("hist"),
            source_document_id=source_document_id,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            event_id=event_id,
            changed_by_type=changed_by_type,
            changed_by_id=changed_by_id,
            changed_at=_now(),
            metadata=metadata or {},
        )
        self._history.append(entry)

        # 6. Update document if status actually changed.
        if old_status != new_status:
            updated = document.model_copy(update={"status": new_status})
            self._registry.update(updated)
            # T-S03-020: source.document.* event.
            event_name = (
                "source.document.registered"
                if new_status == SourceDocumentStatus.REGISTERED
                else "source.document.status_changed"
            )
            self._publish(
                event_type=event_name,
                setup_job_id=updated.setup_job_id,
                message=f"{old_status.value if old_status else None} → {new_status.value}",
                metrics={
                    "source_document_id": source_document_id,
                    "old_status": old_status.value if old_status else None,
                    "new_status": new_status.value,
                    "event_id": event_id,
                },
            )
            # T-S03-022: audit + metrics.
            self._audit_record(
                actor_id=changed_by_id,
                action=AuditAction.STATUS_CHANGED,
                target_type="source_document",
                target_id=source_document_id,
                setup_job_id=updated.setup_job_id,
                payload={
                    "old_status": old_status.value if old_status else None,
                    "new_status": new_status.value,
                    "event_id": event_id,
                    "reason": reason,
                },
            )
            self._inc(
                "source_status_changes_total",
                labels={
                    "from_status": old_status.value if old_status else "none",
                    "to_status": new_status.value,
                },
                help_text="Source document status transitions",
            )
            self._inc(
                "source_documents_total",
                labels={"status": new_status.value},
                help_text="Source documents by status (cumulative on transition)",
            )
            return updated
        return document

    # ============================================================
    # T-S03-010: append_processing_log + link_artifact + get_lineage
    # ============================================================

    def append_processing_log(
        self,
        *,
        source_document_id: str,
        setup_job_id: str,
        step: ProcessingLogStep,
        message: str,
        event_id: str,
        level: ProcessingLogLevel = ProcessingLogLevel.INFO,
        error_code: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SourceProcessingLogEntry:
        """Idempotent через event_id.

        Не делает get документа — log entry может быть записан даже для уже
        удалённого документа (для audit/forensics).
        """
        # T-S03-020/022: snapshot ДО append — чтобы знать был ли это новый log.
        is_new_log = self._log.get_by_event_id(event_id) is None

        entry = SourceProcessingLogEntry(
            processing_log_id=_gen_id("log"),
            source_document_id=source_document_id,
            setup_job_id=setup_job_id,
            step=step,
            level=level,
            message=message,
            error_code=error_code,
            event_id=event_id,
            created_at=_now(),
            payload=payload or {},
        )
        stored = self._log.append(entry)
        # При ERROR публикуем processing_failed + metrics — только для нового лога.
        if (
            level == ProcessingLogLevel.ERROR
            and is_new_log
            and stored.event_id == event_id
        ):
            self._publish(
                event_type="source.document.processing_failed",
                setup_job_id=setup_job_id,
                message=message,
                metrics={
                    "source_document_id": source_document_id,
                    "step": step.value,
                    "error_code": error_code,
                },
            )
            self._inc(
                "source_processing_failures_total",
                labels={
                    "step": step.value,
                    "error_code": error_code or "unknown",
                },
                help_text="Processing failures by step + error_code",
            )
        return stored

    def link_artifact(
        self,
        *,
        source_document_id: str,
        target_type: LineageTargetType,
        target_id: str,
        relation_type: LineageRelationType,
        event_id: str,
        created_by_service: str,
        metadata: dict[str, Any] | None = None,
    ) -> SourceLineageRelation:
        """Создаёт lineage relation (idempotent по двум ключам — см. repo).

        Проверяет существование source document — иначе SourceDocumentNotFoundError.
        Target существование не проверяется (downstream-сервисы пока stub'ы).
        """
        # Защита от dangling lineage: source должен существовать.
        self._registry.get(source_document_id)  # raises if missing

        # T-S03-020: проверяем idempotency ДО link() — чтобы не publish при retry.
        is_new_link = self._lineage.get_by_event_id(event_id) is None

        relation = SourceLineageRelation(
            lineage_id=_gen_id("lin"),
            source_document_id=source_document_id,
            target_type=target_type,
            target_id=target_id,
            relation_type=relation_type,
            created_by_service=created_by_service,
            event_id=event_id,
            created_at=_now(),
            metadata=metadata or {},
        )
        stored = self._lineage.link(relation)
        if is_new_link and stored.event_id == event_id:
            document = self._registry.get(source_document_id)
            self._publish(
                event_type="source.document.lineage_updated",
                setup_job_id=document.setup_job_id,
                message=f"{target_type.value}:{target_id}",
                metrics={
                    "source_document_id": source_document_id,
                    "target_type": target_type.value,
                    "target_id": target_id,
                    "relation_type": relation_type.value,
                },
            )
            # T-S03-022.
            self._audit_record(
                actor_id=created_by_service,
                action=AuditAction.LINEAGE_ADDED,
                target_type="source_document",
                target_id=source_document_id,
                setup_job_id=document.setup_job_id,
                payload={
                    "target_type": target_type.value,
                    "target_id": target_id,
                    "relation_type": relation_type.value,
                    "event_id": event_id,
                },
            )
            self._inc(
                "source_lineage_relations_total",
                labels={
                    "target_type": target_type.value,
                    "relation_type": relation_type.value,
                },
                help_text="Lineage relations by target/relation type",
            )
        return stored

    def get_lineage(
        self, source_document_id: str
    ) -> tuple[list[SourceLineageRelation], object]:
        """Возвращает (relations, counters)."""
        self._registry.get(source_document_id)  # 404 если нет
        relations = self._lineage.list_for_source(source_document_id)
        counters = self._lineage.counters(source_document_id)
        return relations, counters

    # ============================================================
    # T-S03-021: retry_processing
    # ============================================================

    def retry_processing(
        self,
        *,
        source_document_id: str,
        from_step: ProcessingLogStep,
        event_id: str,
        actor_id: str,
        reason: str | None = None,
    ) -> SourceDocument:
        """Reset документа в waiting-статус для повторного запуска downstream.

        - Документ должен быть в PARSE_FAILED или PROCESSING_FAILED.
        - Reset → WAITING_FOR_PARSING (или соответствующее)
        - Append log entry (step=RETRY, level=INFO)
        - Idempotent через event_id (повторный retry с тем же id — no-op).

        В MVP downstream-сервисы (parser, generator) ещё не реализованы —
        endpoint только обновляет статус. Реальный re-trigger pipeline
        появится в SETUP-04+.

        Raises:
            SourceDocumentNotFoundError: документ не найден.
            InvalidStatusTransitionError: текущий статус не failed.
        """
        document = self._registry.get(source_document_id)

        # Только из failed статусов разрешён retry.
        retry_allowed = {
            SourceDocumentStatus.PARSE_FAILED,
            SourceDocumentStatus.PROCESSING_FAILED,
        }
        if document.status not in retry_allowed:
            raise InvalidStatusTransitionError(
                source_document_id=source_document_id,
                old_status=document.status,
                new_status=SourceDocumentStatus.WAITING_FOR_PARSING,
            )

        # Reset → WAITING_FOR_PARSING (validate_transition разрешает).
        updated = self.update_status(
            source_document_id=source_document_id,
            new_status=SourceDocumentStatus.WAITING_FOR_PARSING,
            event_id=f"{event_id}:status",
            reason=reason or f"Manual retry from {from_step.value}",
            changed_by_type=ChangedByType.USER,
            changed_by_id=actor_id,
        )
        self.append_processing_log(
            source_document_id=source_document_id,
            setup_job_id=document.setup_job_id,
            step=ProcessingLogStep.RETRY,
            message=f"Retry triggered by {actor_id} from step={from_step.value}",
            event_id=f"{event_id}:log",
            payload={
                "from_step": from_step.value,
                "reason": reason,
                "actor_id": actor_id,
            },
        )
        # T-S03-022.
        self._audit_record(
            actor_id=actor_id,
            action=AuditAction.PROCESSING_RETRY_TRIGGERED,
            target_type="source_document",
            target_id=source_document_id,
            setup_job_id=document.setup_job_id,
            payload={
                "from_step": from_step.value,
                "reason": reason,
            },
        )
        return updated

    # ============================================================
    # T-S03-011: update_user_metadata
    # ============================================================

    def update_user_metadata(
        self,
        *,
        source_document_id: str,
        patch: UpdateSourceMetadataRequest,
        updated_by: str,
        event_id: str | None = None,
    ) -> SourceDocument:
        """PATCH user metadata.

        - Игнорирует None-поля (partial update).
        - tags/description/etc. сохраняются в document.metadata["user"].
        - Protected fields (checksum, storage_path, status, etc.) защищены
          самой схемой UpdateSourceMetadataRequest (extra="forbid").
        - Дополнительный layer защиты — reject_protected_fields на dict.
        - Записывает processing log entry (INFO, step=metadata_extraction).

        Возвращает обновлённый документ.
        """
        document = self._registry.get(source_document_id)

        # Дополнительная защита (если caller передал raw dict через какой-то
        # внутренний вызов в обход Pydantic).
        patch_dict = patch.model_dump(exclude_none=True)
        reject_protected_fields(patch_dict)

        # Merge with existing user metadata.
        existing_user = document.metadata.get("user", {}) or {}
        if not isinstance(existing_user, dict):
            existing_user = {}
        # Patch-merge: только не-None поля заменяют существующие.
        for field in ("tags", "description", "owner_note", "custom_labels"):
            value = getattr(patch, field)
            if value is not None:
                existing_user[field] = value

        # Прогоняем через SourceDocumentUserMetadata для sanitization (XSS-safe)
        # + per-field length validation. После model_dump получаем чистые значения.
        sanitized = SourceDocumentUserMetadata(**existing_user).model_dump(
            exclude_defaults=False
        )

        new_metadata = dict(document.metadata)
        new_metadata["user"] = sanitized

        updated = document.model_copy(update={"metadata": new_metadata})
        self._registry.update(updated)

        # Audit-trace в processing log.
        log_event_id = event_id or _gen_id("evt_meta")
        self.append_processing_log(
            source_document_id=source_document_id,
            setup_job_id=document.setup_job_id,
            step=ProcessingLogStep.METADATA_EXTRACTION,
            message=f"User metadata updated by {updated_by}",
            event_id=log_event_id,
            payload={"fields_changed": sorted(patch_dict.keys())},
        )
        # T-S03-020.
        self._publish(
            event_type="source.document.metadata_updated",
            setup_job_id=document.setup_job_id,
            message=f"Updated by {updated_by}",
            metrics={
                "source_document_id": source_document_id,
                "fields_changed": sorted(patch_dict.keys()),
                "updated_by": updated_by,
            },
        )
        # T-S03-022.
        self._audit_record(
            actor_id=updated_by,
            action=AuditAction.METADATA_UPDATED,
            target_type="source_document",
            target_id=source_document_id,
            setup_job_id=document.setup_job_id,
            payload={
                "fields_changed": sorted(patch_dict.keys()),
                "updated_by": updated_by,
            },
        )
        return updated


# Re-export для удобства.
__all__ = [
    "InvalidStatusTransitionError",
    "SourceDocumentNotFoundError",
    "SourceLifecycleService",
    "SystemMetadataReadOnlyError",
]
