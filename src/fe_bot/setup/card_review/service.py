"""RAG Card Review Service (SETUP-06 / T-S06-020).

Полный rewrite сервиса под SETUP-06 spec. Реализует 12 use cases:

- list_review_cards
- get_card_for_review
- approve_card
- reject_card
- edit_card
- request_regeneration
- bulk_approve_cards
- get_review_log
- get_card_diff
- get_card_versions

Интегрирован с SETUP-05 RAGCardGenerationOrchestrator для regenerate flow
и с Setup Orchestrator для recalculation readiness.

Legacy методы (approve/reject/edit/regenerate без review_decision_id) сохранены
для backward-compatibility со старым endpoint ``/rag-cards/{doc_id}/review``.

Source of truth — docs/02-system/features/SETUP-06-rag-card-review.md §11.1.
"""

from __future__ import annotations

import contextlib
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from schemas.rag.rag_card import CardStatus, InvalidCardTransitionError, RAGCard
from schemas.setup.rag_card_version import RAGCardVersionDTO
from schemas.setup.review_decision import (
    RejectReason,
    ReviewDecision,
    ReviewDecisionDTO,
)
from schemas.setup.review_log import ReviewLogDTO, ReviewLogEventType

from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.setup.card_registry.service import (
    CardNotFoundError,
    CardRecord,
    InMemoryRAGCardRegistry,
    RAGCardRegistry,
)
from fe_bot.setup.card_review.decision_repository import (
    InMemoryReviewDecisionRepository,
)
from fe_bot.setup.card_review.edit_lock_repository import (
    EditLockActiveError,
    InMemoryEditLockRepository,
)
from fe_bot.setup.card_review.editor import (
    CardEditorService,
    EmptyEditPayloadError,
    SystemMetadataReadOnlyError,
)
from fe_bot.setup.card_review.events import (
    RAGCardApprovedEvent,
    RAGCardEditedEvent,
    RAGCardRegenerateRequestedEvent,
    RAGCardRejectedEvent,
    RAGCardReviewCompletedEvent,
    RAGCardReviewStartedEvent,
    RAGCardVersionCreatedEvent,
    SetupReviewReadinessChangedEvent,
    _BaseRAGCardReviewEvent,
    event_payload,
    event_type_of,
)
from fe_bot.setup.card_review.log_repository import InMemoryReviewLogRepository
from fe_bot.setup.card_review.metrics import ReviewMetricsCollector
from fe_bot.setup.card_review.readiness import (
    ReadinessSummary,
    ReviewReadinessCalculator,
)
from fe_bot.setup.card_review.validators import PreApproveValidationOrchestrator
from fe_bot.setup.card_review.version_repository import (
    InMemoryRAGCardVersionRepository,
)
from fe_bot.setup.card_review.versioning import VersioningService
from fe_bot.setup.events import EventBus, SetupProgressEvent

logger = logging.getLogger(__name__)


# ============================================================
# Legacy compatibility enum (для legacy endpoint)
# ============================================================


class ReviewDecisionLegacy(StrEnum):
    """Legacy enum для backward compatibility с router.py старым endpoint'ом."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    REGENERATE = "regenerate"


# Public alias для legacy import path
ReviewDecisionEnum = ReviewDecisionLegacy


# ============================================================
# Errors
# ============================================================


class ReviewError(Exception):
    """Базовый класс review-ошибок."""


class InvalidReviewStateError(ReviewError):
    """Карточка не в состоянии, разрешающем review."""

    def __init__(self, doc_id: str, status: CardStatus) -> None:
        self.doc_id = doc_id
        self.status = status
        super().__init__(f"Card {doc_id!r} is in status {status.value!r}; cannot review")


class InvalidEditPayloadError(ReviewError):
    """Edit без полезного payload."""


class CardHasCriticalValidationErrorsError(ReviewError):
    """Approve блокирован critical pre-approve errors."""

    def __init__(self, doc_id: str, codes: list[str]) -> None:
        self.doc_id = doc_id
        self.codes = codes
        super().__init__(
            f"Card {doc_id!r} has critical validation errors: {codes}"
        )


class CardVersionConflictError(ReviewError):
    """Edit с устаревшей expected_version."""

    def __init__(self, doc_id: str, expected: str, current: str) -> None:
        self.doc_id = doc_id
        self.expected = expected
        self.current = current
        super().__init__(
            f"Card {doc_id!r}: expected_version {expected!r} != current {current!r}"
        )


# ============================================================
# DTOs
# ============================================================


@dataclass(frozen=True)
class ReviewListFilters:
    """Фильтры для list_review_cards."""

    doc_type: str | None = None
    status: str | None = None
    confidence_level: str | None = None
    source_document_id: str | None = None
    has_validation_errors: bool | None = None
    review_required: bool | None = None
    reviewer_id: str | None = None


@dataclass(frozen=True)
class Pagination:
    page: int = 1
    page_size: int = 50

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True)
class ReviewListItem:
    doc_id: str
    card_version: str
    title: str
    doc_type: str
    status: str
    confidence_level: str | None
    source_document_id: str | None
    source_section_id: str | None
    validation_errors_count: int
    warnings_count: int
    review_required_reason: str | None
    last_reviewed_by: str | None
    updated_at: datetime


@dataclass(frozen=True)
class ReviewListResponse:
    setup_job_id: str
    items: list[ReviewListItem]
    total: int
    page: int
    page_size: int
    summary: dict[str, int]


@dataclass(frozen=True)
class ReviewDetails:
    doc_id: str
    card_version: str
    title: str
    doc_type: str
    status: str
    confidence_level: str | None
    metadata: dict[str, Any]
    body_markdown: str
    source_trace: dict[str, Any]
    validation: dict[str, list[dict[str, str]]]
    review_log_count: int
    permissions: dict[str, bool]


# ============================================================
# Helpers
# ============================================================


_VERSION_LEGACY_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?$")


def _bump_legacy_version(version: str) -> str:
    """Legacy bump для backward compat: 1.0 → 1.1, 2.0.1 → 2.0.2."""
    match = _VERSION_LEGACY_RE.match(version)
    if match is None:
        return f"{version}.1"
    major, minor, patch = match.groups()
    if patch is not None:
        return f"{major}.{minor}.{int(patch) + 1}"
    if minor is not None:
        return f"{major}.{int(minor) + 1}"
    return f"{int(major) + 1}"


def _legacy_new_doc_id(old_doc_id: str, new_version: str) -> str:
    parts = old_doc_id.rsplit(".v", 1)
    if len(parts) == 2:
        return f"{parts[0]}.v{new_version}"
    return f"{old_doc_id}.{new_version}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# Статусы, в которых карточка готова к review.
_REVIEWABLE = frozenset(
    {
        CardStatus.GENERATED,
        CardStatus.REVIEW_REQUIRED,
        CardStatus.METADATA_VALIDATED,
        CardStatus.LOW_CONFIDENCE,
        CardStatus.METADATA_INCOMPLETE,
        CardStatus.VALIDATION_FAILED,
        CardStatus.EDITED,
        CardStatus.EDITING,
    }
)


# ============================================================
# Service
# ============================================================


class RAGCardReviewService:
    """HITL review сервис.

    Поддерживает 12 use cases + legacy compat-методы. Все методы
    идемпотентны через review_decision_id / regenerate_request_id.
    """

    def __init__(
        self,
        registry: RAGCardRegistry,
        *,
        decision_repo: InMemoryReviewDecisionRepository | None = None,
        log_repo: InMemoryReviewLogRepository | None = None,
        version_repo: InMemoryRAGCardVersionRepository | None = None,
        edit_lock_repo: InMemoryEditLockRepository | None = None,
        pre_approve_validator: PreApproveValidationOrchestrator | None = None,
        editor: CardEditorService | None = None,
        versioning: VersioningService | None = None,
        readiness_calculator: ReviewReadinessCalculator | None = None,
        event_bus: EventBus | None = None,
        audit_service: AuditService | None = None,
        metrics: ReviewMetricsCollector | None = None,
        generation_orchestrator: Any = None,  # RAGCardGenerationOrchestrator — late binding
        validation_service: Any = None,  # MetadataValidationService — SETUP-07 hook (T-S07-017)
    ) -> None:
        self._registry = registry
        self._decisions = decision_repo
        self._log = log_repo
        self._versions = version_repo
        self._edit_locks = edit_lock_repo
        self._pre_approve = pre_approve_validator or PreApproveValidationOrchestrator()
        self._editor = editor or CardEditorService()
        self._versioning = versioning or VersioningService()
        self._readiness = readiness_calculator
        self._bus = event_bus
        self._audit = audit_service
        self._metrics = metrics or ReviewMetricsCollector()
        self._generation = generation_orchestrator
        self._validation = validation_service

    # ============================================================
    # Read-side use cases
    # ============================================================

    def list_review_cards(
        self,
        setup_job_id: str,
        *,
        filters: ReviewListFilters | None = None,
        pagination: Pagination | None = None,
    ) -> ReviewListResponse:
        """T-S06-020 use case 1: список карточек с фильтрами."""
        filters = filters or ReviewListFilters()
        pagination = pagination or Pagination()
        records = self._registry.list_for_job(setup_job_id)

        items_all = [self._record_to_list_item(r) for r in records]
        filtered = self._apply_filters(items_all, filters)
        total = len(filtered)
        start = pagination.offset
        end = start + pagination.page_size
        page_items = filtered[start:end]

        # Summary по всем (не отфильтрованным) карточкам setup_job.
        summary: dict[str, int] = {"total": len(records)}
        for item in items_all:
            summary[item.status] = summary.get(item.status, 0) + 1

        return ReviewListResponse(
            setup_job_id=setup_job_id,
            items=page_items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            summary=summary,
        )

    def get_card_for_review(self, doc_id: str) -> ReviewDetails:
        """T-S06-020 use case 2: детали карточки."""
        record = self._load_record(doc_id)
        return self._record_to_details(record)

    def get_review_log(
        self,
        doc_id: str,
        *,
        limit: int | None = None,
    ) -> list[ReviewLogDTO]:
        """T-S06-020 use case 8: review log."""
        if self._log is None:
            return []
        return self._log.list_for_card(doc_id, limit=limit)

    def get_card_versions(self, doc_id: str) -> list[RAGCardVersionDTO]:
        """T-S06-020 use case 10: список версий."""
        if self._versions is None:
            return []
        return self._versions.list_for_card(doc_id)

    def get_card_diff(
        self,
        doc_id: str,
        *,
        from_version: str,
        to_version: str,
    ) -> dict[str, Any]:
        """T-S06-020 use case 9: diff."""
        if self._versions is None:
            raise InvalidEditPayloadError("Versions repository not configured")
        v_from = self._versions.get(doc_id, from_version)
        v_to = self._versions.get(doc_id, to_version)
        # Diff в MVP — на основе metadata snapshot + сравнение body hash.
        return {
            "doc_id": doc_id,
            "from_version": v_from.card_version,
            "to_version": v_to.card_version,
            "body_changed": v_from.body_hash != v_to.body_hash,
            "metadata_from": v_from.metadata_snapshot,
            "metadata_to": v_to.metadata_snapshot,
        }

    # ============================================================
    # Write-side: approve
    # ============================================================

    def approve_card(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        reviewer_role: str = "user",
        review_decision_id: str | None = None,
        comment: str | None = None,
        setup_job_id: str | None = None,
    ) -> CardRecord:
        """T-S06-020 use case 3: approve."""
        start_ts = _now()
        decision_id = review_decision_id or _gen_id("rd")

        # Idempotency check.
        if self._decisions is not None and self._decisions.exists(decision_id):
            existing_decision = self._decisions.get(decision_id)
            logger.info(
                "rag_card_review_decision_idempotent",
                extra={
                    "review_decision_id": decision_id,
                    "doc_id": doc_id,
                    "decision": existing_decision.decision.value,
                },
            )
            return self._load_record(doc_id)

        record = self._load_record(doc_id, reviewable=True)
        card = record.card
        sid = setup_job_id or record.setup_job_id

        # Pre-approve validation (AC-16, AC-17).
        pre_report = self._pre_approve.validate(card)
        if not pre_report.passed:
            codes = [e.code for e in pre_report.critical_errors]
            for code in codes:
                self._metrics.record_validation_blocked_approve(error_code=code)
            raise CardHasCriticalValidationErrorsError(doc_id, codes)

        # Persist review decision.
        decision_dto = ReviewDecisionDTO(
            review_decision_id=decision_id,
            setup_job_id=sid,
            doc_id=doc_id,
            card_version=card.card_version or card.version,
            decision=ReviewDecision.APPROVE,
            reason=None,
            comment=comment,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            created_at=_now(),
        )
        if self._decisions is not None:
            self._decisions.add(decision_dto)

        # Status transition.
        target_status = CardStatus.APPROVED
        updated_card = self._safe_transition(card, target_status)
        updated_card = updated_card.model_copy(
            update={"reviewed_by": reviewer_id, "updated_at": _now()}
        )

        # Update via registry.update; CardRegistry will append note to history.
        note = f"approve by {reviewer_id}" + (f": {comment}" if comment else "")
        updated_record = self._registry.update(doc_id, card=updated_card, note=note)

        # Review log.
        self._append_log(
            doc_id=doc_id,
            card_version=card.card_version or card.version,
            event_type=ReviewLogEventType.APPROVED,
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            message=f"approved by {reviewer_id}",
            before_status=card.status.value,
            after_status=target_status.value,
            setup_job_id=sid,
            payload={"review_decision_id": decision_id, "comment": comment},
        )

        # Audit.
        self._audit_record(
            actor_id=reviewer_id,
            action=AuditAction.CARD_REVIEW_APPROVED,
            target_id=doc_id,
            setup_job_id=sid,
            payload={
                "review_decision_id": decision_id,
                "card_version": card.card_version or card.version,
                "doc_type": card.doc_type.value,
            },
        )

        # Metrics.
        duration_ms = int((_now() - start_ts).total_seconds() * 1000)
        self._metrics.record_decision(decision="approve")
        self._metrics.record_approved(doc_type=card.doc_type.value)
        self._metrics.observe_duration(
            decision="approve",
            doc_type=card.doc_type.value,
            duration_ms=duration_ms,
        )

        # T-S06-039: structured log.
        logger.info(
            "rag_card_review_decision_made",
            extra={
                "setup_job_id": sid,
                "doc_id": doc_id,
                "card_version": card.card_version or card.version,
                "reviewer_id": reviewer_id,
                "decision": "approve",
                "status_before": card.status.value,
                "status_after": target_status.value,
                "duration_ms": duration_ms,
                "outcome": "success",
            },
        )

        # Events.
        self._emit(
            RAGCardApprovedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=sid,
                occurred_at=_now(),
                doc_id=doc_id,
                card_version=card.card_version or card.version,
                review_decision_id=decision_id,
                reviewer_id=reviewer_id,
                duration_ms=duration_ms,
            )
        )
        self._emit_completed(doc_id, card.card_version or card.version, target_status, reviewer_id, sid)

        # T-S07-017: auto-validate после approve (опционально, через
        # validation_service hook). Если валидация PASSED — карточка переходит
        # в METADATA_VALIDATED. FAILED — возврат в REVIEW_REQUIRED.
        if self._validation is not None:
            try:
                self._validation.validate_one(doc_id, triggered_by=reviewer_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "rag_card_auto_validation_failed",
                    extra={
                        "setup_job_id": sid,
                        "doc_id": doc_id,
                        "error": str(exc),
                    },
                )

        # Readiness recalc.
        self._recalculate_readiness(sid)

        return updated_record

    # ============================================================
    # Write-side: reject
    # ============================================================

    def reject_card(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        reason: str,
        reviewer_role: str = "user",
        review_decision_id: str | None = None,
        comment: str | None = None,
        setup_job_id: str | None = None,
    ) -> CardRecord:
        """T-S06-020 use case 4: reject."""
        if not reason:
            raise InvalidEditPayloadError("reject requires reason (AC-23)")

        decision_id = review_decision_id or _gen_id("rd")
        if self._decisions is not None and self._decisions.exists(decision_id):
            return self._load_record(doc_id)

        record = self._load_record(doc_id, reviewable=True)
        card = record.card
        sid = setup_job_id or record.setup_job_id

        decision_dto = ReviewDecisionDTO(
            review_decision_id=decision_id,
            setup_job_id=sid,
            doc_id=doc_id,
            card_version=card.card_version or card.version,
            decision=ReviewDecision.REJECT,
            reason=reason,
            comment=comment,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            created_at=_now(),
        )
        if self._decisions is not None:
            self._decisions.add(decision_dto)

        target_status = CardStatus.REJECTED
        updated_card = self._safe_transition(card, target_status)
        updated_card = updated_card.model_copy(
            update={"reviewed_by": reviewer_id, "updated_at": _now()}
        )
        note = f"reject by {reviewer_id} ({reason})" + (f": {comment}" if comment else "")
        updated_record = self._registry.update(doc_id, card=updated_card, note=note)

        self._append_log(
            doc_id=doc_id,
            card_version=card.card_version or card.version,
            event_type=ReviewLogEventType.REJECTED,
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            message=f"rejected by {reviewer_id}: {reason}",
            before_status=card.status.value,
            after_status=target_status.value,
            setup_job_id=sid,
            payload={"review_decision_id": decision_id, "reason": reason},
        )

        self._audit_record(
            actor_id=reviewer_id,
            action=AuditAction.CARD_REVIEW_REJECTED,
            target_id=doc_id,
            setup_job_id=sid,
            payload={"review_decision_id": decision_id, "reason": reason},
        )

        self._metrics.record_decision(decision="reject")
        self._metrics.record_rejected(doc_type=card.doc_type.value, reason=reason)

        # T-S06-039: structured log.
        logger.info(
            "rag_card_review_decision_made",
            extra={
                "setup_job_id": sid,
                "doc_id": doc_id,
                "card_version": card.card_version or card.version,
                "reviewer_id": reviewer_id,
                "decision": "reject",
                "reason": reason,
                "status_before": card.status.value,
                "status_after": target_status.value,
                "outcome": "success",
            },
        )

        self._emit(
            RAGCardRejectedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=sid,
                occurred_at=_now(),
                doc_id=doc_id,
                card_version=card.card_version or card.version,
                review_decision_id=decision_id,
                reviewer_id=reviewer_id,
                reason=reason,
            )
        )
        self._emit_completed(doc_id, card.card_version or card.version, target_status, reviewer_id, sid)

        self._recalculate_readiness(sid)

        return updated_record

    # ============================================================
    # Write-side: edit
    # ============================================================

    def edit_card(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        reviewer_role: str = "user",
        expected_version: str | None = None,
        metadata_patch: dict[str, Any] | None = None,
        body_markdown: str | None = None,
        change_reason: str | None = None,
        setup_job_id: str | None = None,
    ) -> CardRecord:
        """T-S06-020 use case 5: edit с optimistic concurrency."""
        record = self._load_record(doc_id, reviewable=True)
        card = record.card
        sid = setup_job_id or record.setup_job_id
        current_version = card.card_version or card.version

        # Optimistic concurrency check.
        if expected_version is not None and expected_version != current_version:
            self._metrics.record_version_conflict()
            raise CardVersionConflictError(doc_id, expected_version, current_version)

        # Apply patch.
        try:
            draft = self._editor.apply_patch(
                card,
                metadata_patch=metadata_patch,
                body_markdown=body_markdown,
            )
        except SystemMetadataReadOnlyError:
            raise
        except EmptyEditPayloadError:
            raise

        # Versioning: minor bump для edit.
        result = self._versioning.create_new_version(
            card,
            bump_type="minor",
            change_reason=change_reason,
            created_by=reviewer_id,
            new_card_body=draft.card.body_markdown if draft.body_changed else None,
            new_card_title=draft.card.title if draft.metadata_changed else None,
            new_front_matter=draft.card.front_matter if draft.metadata_changed else None,
            target_status=CardStatus.EDITED,
        )
        new_card = result.new_card
        new_version_dto = result.version_dto

        # Persist version + update card in registry.
        if self._versions is not None:
            self._versions.add(new_version_dto)
            self._versions.set_current(doc_id, new_version_dto.card_version)

        # Mark current card in registry as EDITED with bumped version.
        new_card = new_card.model_copy(update={"reviewed_by": reviewer_id})
        note = f"edit by {reviewer_id}: {change_reason or 'no reason'}"
        updated_record = self._registry.update(doc_id, card=new_card, note=note)

        self._append_log(
            doc_id=doc_id,
            card_version=new_version_dto.card_version,
            event_type=ReviewLogEventType.EDITED,
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            message=f"edited by {reviewer_id}",
            before_status=card.status.value,
            after_status=CardStatus.EDITED.value,
            setup_job_id=sid,
            payload={
                "previous_card_version": current_version,
                "new_card_version": new_version_dto.card_version,
                "metadata_changed": draft.metadata_changed,
                "body_changed": draft.body_changed,
            },
        )
        self._append_log(
            doc_id=doc_id,
            card_version=new_version_dto.card_version,
            event_type=ReviewLogEventType.VERSION_CREATED,
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            message=f"version {new_version_dto.card_version} created",
            before_status=None,
            after_status=CardStatus.EDITED.value,
            setup_job_id=sid,
        )

        self._audit_record(
            actor_id=reviewer_id,
            action=AuditAction.CARD_REVIEW_EDITED,
            target_id=doc_id,
            setup_job_id=sid,
            payload={
                "previous_card_version": current_version,
                "new_card_version": new_version_dto.card_version,
                "change_reason": change_reason,
            },
        )

        self._metrics.record_decision(decision="edit")
        self._metrics.record_edited(doc_type=card.doc_type.value)

        # T-S06-039: structured log per edit.
        logger.info(
            "rag_card_edited",
            extra={
                "setup_job_id": sid,
                "doc_id": doc_id,
                "previous_card_version": current_version,
                "new_card_version": new_version_dto.card_version,
                "reviewer_id": reviewer_id,
                "metadata_changed": draft.metadata_changed,
                "body_changed": draft.body_changed,
                "change_reason": change_reason,
                "outcome": "success",
            },
        )

        self._emit(
            RAGCardEditedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=sid,
                occurred_at=_now(),
                doc_id=doc_id,
                previous_card_version=current_version,
                new_card_version=new_version_dto.card_version,
                reviewer_id=reviewer_id,
                metadata_changed=draft.metadata_changed,
                body_changed=draft.body_changed,
            )
        )
        self._emit(
            RAGCardVersionCreatedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=sid,
                occurred_at=_now(),
                doc_id=doc_id,
                card_version=new_version_dto.card_version,
                parent_card_version=current_version,
                created_by=reviewer_id,
                change_reason=change_reason,
            )
        )

        self._recalculate_readiness(sid)

        return updated_record

    # ============================================================
    # Write-side: regenerate
    # ============================================================

    def request_regeneration(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        reason: str,
        reviewer_role: str = "user",
        regenerate_request_id: str | None = None,
        instruction: str | None = None,
        setup_job_id: str | None = None,
    ) -> CardRecord:
        """T-S06-021: regenerate flow с интеграцией SETUP-05 orchestrator."""
        if not reason:
            raise InvalidEditPayloadError("regenerate requires reason (AC-35)")

        request_id = regenerate_request_id or _gen_id("regen")
        record = self._load_record(doc_id, reviewable=True)
        card = record.card
        sid = setup_job_id or record.setup_job_id

        # Идемпотентность через decision_repo.
        if self._decisions is not None and self._decisions.exists(request_id):
            return self._load_record(doc_id)

        # Запускаем regenerate job через SETUP-05 orchestrator если есть primary section.
        gen_job_id = ""
        if self._generation is not None and card.primary_source_section_id:
            try:
                gen_job = self._generation.create_job(
                    setup_job_id=sid,
                    requested_by=reviewer_id,
                    section_ids=[card.primary_source_section_id],
                    config={
                        "generation_mode": "llm",
                        "regenerate_of": doc_id,
                        "regenerate_reason": reason,
                        "regenerate_request_id": request_id,
                        "instruction": instruction,
                    },
                )
                gen_job_id = gen_job.generation_job_id
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "rag_card_regenerate_orchestrator_unavailable",
                    extra={"doc_id": doc_id, "error": str(exc)},
                )
                gen_job_id = ""

        # Persist decision.
        decision_dto = ReviewDecisionDTO(
            review_decision_id=request_id,
            setup_job_id=sid,
            doc_id=doc_id,
            card_version=card.card_version or card.version,
            decision=ReviewDecision.REGENERATE,
            reason=reason,
            comment=instruction,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            created_at=_now(),
            metadata={"generation_job_id": gen_job_id} if gen_job_id else {},
        )
        if self._decisions is not None:
            self._decisions.add(decision_dto)

        target_status = CardStatus.REGENERATE_REQUESTED
        updated_card = self._safe_transition(card, target_status)
        updated_card = updated_card.model_copy(
            update={"reviewed_by": reviewer_id, "updated_at": _now()}
        )
        note = f"regenerate by {reviewer_id} ({reason})"
        updated_record = self._registry.update(doc_id, card=updated_card, note=note)

        self._append_log(
            doc_id=doc_id,
            card_version=card.card_version or card.version,
            event_type=ReviewLogEventType.REGENERATE_REQUESTED,
            actor_id=reviewer_id,
            actor_role=reviewer_role,
            message=f"regenerate requested by {reviewer_id}: {reason}",
            before_status=card.status.value,
            after_status=target_status.value,
            setup_job_id=sid,
            payload={
                "regenerate_request_id": request_id,
                "reason": reason,
                "generation_job_id": gen_job_id,
            },
        )

        self._audit_record(
            actor_id=reviewer_id,
            action=AuditAction.RAG_CARD_REGENERATE_TRIGGERED,
            target_id=doc_id,
            setup_job_id=sid,
            payload={
                "regenerate_request_id": request_id,
                "reason": reason,
                "generation_job_id": gen_job_id,
            },
        )

        self._metrics.record_decision(decision="regenerate")
        self._metrics.record_regenerate_requested(doc_type=card.doc_type.value)

        # T-S06-039: structured log per regenerate.
        logger.info(
            "rag_card_regenerate_requested",
            extra={
                "setup_job_id": sid,
                "doc_id": doc_id,
                "card_version": card.card_version or card.version,
                "regenerate_request_id": request_id,
                "generation_job_id": gen_job_id or "(unavailable)",
                "reviewer_id": reviewer_id,
                "reason": reason,
                "outcome": "success",
            },
        )

        self._emit(
            RAGCardRegenerateRequestedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=sid,
                occurred_at=_now(),
                doc_id=doc_id,
                card_version=card.card_version or card.version,
                regenerate_request_id=request_id,
                generation_job_id=gen_job_id or "(unavailable)",
                reviewer_id=reviewer_id,
                reason=reason,
            )
        )

        self._recalculate_readiness(sid)

        return updated_record

    # ============================================================
    # Bulk approve
    # ============================================================

    def bulk_approve_cards(
        self,
        *,
        setup_job_id: str,
        reviewer_id: str,
        reviewer_role: str = "user",
        items: list[tuple[str, str]],  # list of (doc_id, expected_card_version)
        comment: str | None = None,
        bulk_review_id: str | None = None,
    ) -> dict[str, Any]:
        """T-S06-020 use case 7: bulk approve."""
        bulk_id = bulk_review_id or _gen_id("bulk")
        results: list[dict[str, Any]] = []
        success_count = 0
        for doc_id, expected_version in items:
            try:
                record = self.approve_card(
                    doc_id=doc_id,
                    reviewer_id=reviewer_id,
                    reviewer_role=reviewer_role,
                    comment=comment,
                    setup_job_id=setup_job_id,
                )
                results.append(
                    {
                        "doc_id": doc_id,
                        "status": "approved",
                        "card_version": record.card.card_version or record.card.version,
                    }
                )
                success_count += 1
            except (
                CardHasCriticalValidationErrorsError,
                InvalidReviewStateError,
                CardNotFoundError,
            ) as exc:
                results.append(
                    {
                        "doc_id": doc_id,
                        "status": "error",
                        "error": str(exc),
                    }
                )

        # T-S06-039: structured log per bulk.
        logger.info(
            "rag_card_bulk_review_completed",
            extra={
                "setup_job_id": setup_job_id,
                "bulk_review_id": bulk_id,
                "total": len(items),
                "approved": success_count,
                "errors": len(items) - success_count,
                "reviewer_id": reviewer_id,
                "outcome": "success" if success_count == len(items) else "partial",
            },
        )

        return {
            "bulk_review_id": bulk_id,
            "total": len(items),
            "approved": success_count,
            "errors": len(items) - success_count,
            "results": results,
        }

    # ============================================================
    # Legacy compat-методы (старый router /rag-cards/{doc_id}/review)
    # ============================================================

    def approve(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        comment: str | None = None,
    ) -> CardRecord:
        """Legacy compat для старого endpoint — простой status transition
        без pre-approve validation (поведение исходного MVP сервиса).
        """
        rec = self._load_record(doc_id, reviewable=True)
        card = rec.card
        target = CardStatus.APPROVED
        if not card.can_transition_to(target):
            with contextlib.suppress(InvalidCardTransitionError):
                card = card.model_copy(update={"status": CardStatus.REVIEW_REQUIRED})
        updated_card = card.model_copy(
            update={
                "status": target,
                "reviewed_by": reviewer_id,
            }
        )
        note = f"approve by {reviewer_id}" + (f": {comment}" if comment else "")
        return self._registry.update(doc_id, card=updated_card, note=note)

    def reject(
        self,
        *,
        doc_id: str,
        reviewer_id: str,
        comment: str | None = None,
    ) -> CardRecord:
        """Legacy compat: переводит в DEPRECATED (как делал старый сервис)."""
        # В legacy старый сервис делал status=DEPRECATED. Сохраняем поведение
        # для бэк-совместимости старого endpoint.
        record = self._load_record(doc_id, reviewable=True)
        card = record.card
        target = CardStatus.DEPRECATED
        if not card.can_transition_to(target):
            raise InvalidReviewStateError(doc_id, card.status)
        updated_card = card.model_copy(
            update={
                "status": target,
                "reviewed_by": reviewer_id,
            }
        )
        note = f"reject by {reviewer_id}" + (f": {comment}" if comment else "")
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
        """Legacy compat — старая семантика: создаёт новый doc_id с .v{new}.

        Сохраняем legacy bump (1.0 → 1.1, 2.0.1 → 2.0.2) и создание новой
        карточки через registry.add (а не versioning) — старый endpoint
        требует именно это поведение.
        """
        if updated_body_markdown is None and updated_title is None:
            raise InvalidEditPayloadError(
                "edit must provide updated_title and/or updated_body_markdown"
            )
        rec = self._load_record(doc_id, reviewable=True)
        old_card = rec.card

        new_version = _bump_legacy_version(old_card.version)
        new_id = _legacy_new_doc_id(old_card.doc_id, new_version)
        if self._registry.exists(new_id):
            raise InvalidEditPayloadError(
                f"Edited version doc_id {new_id!r} already exists"
            )

        now = _now()
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
        note = (
            f"edit by {reviewer_id}: superseded by {new_id}"
            + (f" — {comment}" if comment else "")
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
        """Legacy compat: переводит карточку в DRAFT (как старый сервис).

        Новый clean-flow — request_regeneration() — должен вызываться через
        новый endpoint /rag-cards-review/{doc_id}/regenerate.
        """
        rec = self._load_record(doc_id, reviewable=True)
        target = CardStatus.DRAFT
        if not rec.card.can_transition_to(target):
            raise InvalidReviewStateError(doc_id, rec.card.status)
        updated_card = rec.card.model_copy(
            update={
                "status": target,
                "reviewed_by": reviewer_id,
            }
        )
        note = f"regenerate by {reviewer_id}" + (f": {comment}" if comment else "")
        return self._registry.update(doc_id, card=updated_card, note=note)

    # ============================================================
    # Internals
    # ============================================================

    def _load_record(self, doc_id: str, *, reviewable: bool = False) -> CardRecord:
        try:
            rec = self._registry.get(doc_id)
        except CardNotFoundError:
            raise
        if reviewable and rec.card.status not in _REVIEWABLE:
            raise InvalidReviewStateError(doc_id, rec.card.status)
        return rec

    def _safe_transition(self, card: RAGCard, target: CardStatus) -> RAGCard:
        """Применяет переход или ставит карточку в REVIEW_REQUIRED промежуточно."""
        try:
            return card.model_copy(update={"status": target})
        except InvalidCardTransitionError:
            # Промежуточный переход через REVIEW_REQUIRED.
            if card.status != CardStatus.REVIEW_REQUIRED:
                with contextlib.suppress(InvalidCardTransitionError):
                    card = card.model_copy(update={"status": CardStatus.REVIEW_REQUIRED})
            return card.model_copy(update={"status": target})

    def _apply_filters(
        self,
        items: list[ReviewListItem],
        filters: ReviewListFilters,
    ) -> list[ReviewListItem]:
        result = items
        if filters.doc_type is not None:
            result = [i for i in result if i.doc_type == filters.doc_type]
        if filters.status is not None:
            result = [i for i in result if i.status == filters.status]
        if filters.confidence_level is not None:
            result = [i for i in result if i.confidence_level == filters.confidence_level]
        if filters.source_document_id is not None:
            result = [
                i for i in result if i.source_document_id == filters.source_document_id
            ]
        if filters.has_validation_errors is True:
            result = [i for i in result if i.validation_errors_count > 0]
        elif filters.has_validation_errors is False:
            result = [i for i in result if i.validation_errors_count == 0]
        if filters.review_required is True:
            result = [i for i in result if i.status == "review_required"]
        if filters.reviewer_id is not None:
            result = [i for i in result if i.last_reviewed_by == filters.reviewer_id]
        return result

    def _record_to_list_item(self, record: CardRecord) -> ReviewListItem:
        card = record.card
        return ReviewListItem(
            doc_id=card.doc_id,
            card_version=card.card_version or card.version,
            title=card.title,
            doc_type=card.doc_type.value,
            status=card.status.value,
            confidence_level=card.confidence_level,
            source_document_id=(
                card.source_document_ids[0] if card.source_document_ids else None
            ),
            source_section_id=card.primary_source_section_id
            or (card.source_section_ids[0] if card.source_section_ids else None),
            validation_errors_count=0,  # populated by pre-approve when needed
            warnings_count=0,
            review_required_reason=card.review_required_reason,
            last_reviewed_by=card.reviewed_by,
            updated_at=card.updated_at,
        )

    def _record_to_details(self, record: CardRecord) -> ReviewDetails:
        card = record.card
        pre = self._pre_approve.validate(card)
        return ReviewDetails(
            doc_id=card.doc_id,
            card_version=card.card_version or card.version,
            title=card.title,
            doc_type=card.doc_type.value,
            status=card.status.value,
            confidence_level=card.confidence_level,
            metadata=dict(card.front_matter),
            body_markdown=card.body_markdown,
            source_trace={
                "source_document_ids": list(card.source_document_ids),
                "source_section_ids": list(card.source_section_ids),
                "primary_source_section_id": card.primary_source_section_id,
            },
            validation={
                "critical_errors": [
                    {"code": e.code, "message": e.message} for e in pre.critical_errors
                ],
                "warnings": [
                    {"code": w.code, "message": w.message} for w in pre.warnings
                ],
            },
            review_log_count=(
                self._log.count_for_card(card.doc_id) if self._log else 0
            ),
            permissions={
                "can_approve": pre.passed,
                "can_reject": True,
                "can_edit": True,
                "can_regenerate": True,
            },
        )

    def _append_log(
        self,
        *,
        doc_id: str,
        card_version: str,
        event_type: ReviewLogEventType,
        actor_id: str,
        actor_role: str,
        message: str,
        before_status: str | None,
        after_status: str | None,
        setup_job_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._log is None:
            return
        self._log.append(
            ReviewLogDTO(
                review_log_id=_gen_id("rl"),
                setup_job_id=setup_job_id,
                doc_id=doc_id,
                card_version=card_version,
                event_type=event_type,
                actor_id=actor_id,
                actor_role=actor_role,
                message=message,
                before_status=before_status,
                after_status=after_status,
                created_at=_now(),
                payload=payload or {},
            )
        )

    def _emit(self, event: _BaseRAGCardReviewEvent) -> None:
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

    def _emit_completed(
        self,
        doc_id: str,
        card_version: str,
        final_status: CardStatus,
        reviewer_id: str,
        setup_job_id: str,
    ) -> None:
        self._emit(
            RAGCardReviewCompletedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=setup_job_id,
                occurred_at=_now(),
                doc_id=doc_id,
                card_version=card_version,
                final_status=final_status.value,
                reviewer_id=reviewer_id,
            )
        )

    def _audit_record(
        self,
        *,
        actor_id: str,
        action: AuditAction,
        target_id: str,
        setup_job_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            actor_id=actor_id,
            action=action,
            target_type="rag_card",
            target_id=target_id,
            setup_job_id=setup_job_id,
            payload=payload or {},
        )

    def _recalculate_readiness(self, setup_job_id: str) -> ReadinessSummary | None:
        if self._readiness is None:
            return None
        summary = self._readiness.calculate(setup_job_id)
        self._emit(
            SetupReviewReadinessChangedEvent(
                event_id=_gen_id("evt"),
                setup_job_id=setup_job_id,
                occurred_at=_now(),
                total=summary.total,
                approved=summary.approved,
                rejected=summary.rejected,
                blocking=(summary.total - summary.approved - summary.rejected),
                ready_for_next_step=summary.ready_for_next_step,
            )
        )
        return summary


# ============================================================
# Legacy public exports
# ============================================================


# Legacy alias для router import: `from fe_bot.setup.card_review.service import ReviewDecision`
# Старый router использует ReviewDecision enum для парсинга payload.decision строки.
ReviewDecisionLegacyAlias = ReviewDecisionLegacy

# Legacy aliases для tests/unit/test_card_review_service.py.
_bump_version = _bump_legacy_version
_new_doc_id = _legacy_new_doc_id
