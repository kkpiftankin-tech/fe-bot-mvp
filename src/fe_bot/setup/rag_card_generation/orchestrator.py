"""RAGCardGenerationOrchestrator (SETUP-05 / T-S05-023).

Координатор генерации RAG-карточек:

1. ``create_job(setup_job_id, requested_by, *, section_ids, config)`` —
   создаёт RAGCardGenerationJob поверх ParsedSection'ов одного setup_job_id.
2. ``run(generation_job_id)`` — синхронный pipeline:
     ParsedSection → DocTypeDetector → MetadataExtractor → OntologyMapper →
     PromptTemplateRegistry → LLMCardAdapter → MarkdownBuilder →
     CardValidationPrecheck → ConfidenceCalculator → save card+metadata+artifact
     + lineage + processing_log + events.
3. Lineage: ``SourceLifecycleService.link_artifact(target_type=RAG_CARD,
   relation_type=GENERATED_FROM)``.
4. Status updates SourceDocument: SECTIONS_EXTRACTED → RAG_CARDS_GENERATING
   → RAG_CARDS_GENERATED.
5. Metrics (4): rag_card_generation_jobs_total, rag_cards_generated_total,
   rag_cards_failed_total, rag_card_generation_duration_ms.

Sync in-process MVP (как в SETUP-04 DocumentParserOrchestrator).
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # SETUP-12: только для type-checking, чтобы не создавать runtime-зависимость
    # rag_card_generation → taxonomy (см. TaxonomyDocTypeDetector, который
    # зависит от rag_card_generation.doc_type_detector в обратную сторону).
    from fe_bot.taxonomy.registry import TaxonomyRegistry

from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.setup.lineage import LineageRelationType, LineageTargetType
from schemas.setup.parsed_section import ParsedSection, ParsedSectionStatus
from schemas.setup.processing_log import ProcessingLogLevel, ProcessingLogStep
from schemas.setup.rag_card_generation_job import (
    RAGCardGenerationErrorCode,
    RAGCardGenerationJob,
    RAGCardGenerationJobStatus,
)
from schemas.setup.rag_card_generation_job_section import (
    CardConfidenceLevel,
    RAGCardGenerationJobSection,
    RAGCardGenerationJobSectionStatus,
)
from schemas.setup.rag_card_generation_report import (
    CardGenerationReportDTO,
    CardGenerationSummary,
)
from schemas.setup.rag_card_metadata import RAGCardMetadataDTO
from schemas.setup.rag_card_source_link import RAGCardSourceLinkDTO
from schemas.setup.source_document import SourceDocumentStatus

from fe_bot.audit.service import AuditAction, AuditService
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.setup.card_registry.service import (
    CardAlreadyExistsError,
    InMemoryRAGCardRegistry,
)
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.rag_card_generation.confidence_calculator import (
    ConfidenceCalculator,
    ConfidenceDecision,
)
from fe_bot.setup.rag_card_generation.doc_id_generator import DocIdGenerator
from fe_bot.setup.rag_card_generation.doc_type_detector import DocTypeDetector
from fe_bot.setup.rag_card_generation.events import (
    RAGCardGeneratedEvent,
    RAGCardGenerationFailedEvent,
    RAGCardGenerationJobCompletedEvent,
    RAGCardGenerationJobCreatedEvent,
    RAGCardGenerationJobFailedEvent,
    RAGCardGenerationJobPartialSuccessEvent,
    RAGCardGenerationJobStartedEvent,
    RAGCardReviewRequiredEvent,
    _BaseRAGCardGenerationEvent,
    event_payload,
    event_type_of,
)
from fe_bot.setup.rag_card_generation.job_repository import (
    DuplicateRAGCardGenerationJobError,
    InMemoryRAGCardGenerationJobRepository,
)
from fe_bot.setup.rag_card_generation.job_section_repository import (
    InMemoryRAGCardGenerationJobSectionRepository,
)
from fe_bot.setup.rag_card_generation.llm_adapter import (
    LLMCardAdapter,
    LLMCardGenerationFailed,
)
from fe_bot.setup.rag_card_generation.markdown_builder import build_markdown
from fe_bot.setup.rag_card_generation.metadata_extractor import (
    MetadataCandidates,
    MetadataExtractor,
)
from fe_bot.setup.rag_card_generation.ontology_mapper import (
    OntologyMapper,
    OntologyWarning,
)
from fe_bot.setup.rag_card_generation.precheck import (
    CardValidationPrecheck,
    RAGCardDraft,
)
from fe_bot.setup.rag_card_generation.prompt_registry import (
    PromptContext,
    PromptTemplateNotFoundError,
    PromptTemplateRegistry,
)
from fe_bot.setup.rag_card_generation.report_repository import (
    InMemoryCardGenerationReportRepository,
)
from fe_bot.setup.rag_card_generation.source_link_repository import (
    InMemoryRAGCardSourceLinkRepository,
)
from fe_bot.setup.source_registry.lifecycle import SourceLifecycleService
from fe_bot.storage.artifact_service import ArtifactStorage

logger = logging.getLogger(__name__)

_DEFAULT_CONFIDENCE_THRESHOLD = 0.7

# Какие статусы ParsedSection считаем готовыми к генерации карточки.
_SECTION_READY_STATUSES = frozenset(
    {
        ParsedSectionStatus.CLASSIFIED,
        ParsedSectionStatus.EXTRACTED,
    }
)


# ============================================================
# Errors
# ============================================================


class RAGCardGenerationAlreadyRunningError(Exception):
    """Активный RAGCardGenerationJob уже существует для setup_job_id."""

    def __init__(self, setup_job_id: str, active_generation_job_id: str) -> None:
        self.setup_job_id = setup_job_id
        self.active_generation_job_id = active_generation_job_id
        super().__init__(
            f"Active RAGCardGenerationJob {active_generation_job_id} "
            f"already exists for setup_job {setup_job_id}"
        )


class NoSectionsReadyError(Exception):
    """Нет ParsedSection'ов, готовых к генерации карточек."""

    def __init__(self, setup_job_id: str) -> None:
        self.setup_job_id = setup_job_id
        super().__init__(f"No sections ready for card generation in setup_job {setup_job_id}")


# ============================================================
# Internal value
# ============================================================


class _SectionOutcome:
    __slots__ = ("status", "confidence", "doc_type", "review_required")

    def __init__(
        self,
        *,
        status: RAGCardGenerationJobSectionStatus,
        confidence: CardConfidenceLevel | None,
        doc_type: str | None,
        review_required: bool,
    ) -> None:
        self.status = status
        self.confidence = confidence
        self.doc_type = doc_type
        self.review_required = review_required


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ============================================================
# Orchestrator
# ============================================================


class RAGCardGenerationOrchestrator:
    """Координатор генерации RAG-карточек (синхронный MVP)."""

    def __init__(
        self,
        *,
        job_repo: InMemoryRAGCardGenerationJobRepository,
        job_section_repo: InMemoryRAGCardGenerationJobSectionRepository,
        card_registry: InMemoryRAGCardRegistry,
        source_link_repo: InMemoryRAGCardSourceLinkRepository,
        report_repo: InMemoryCardGenerationReportRepository,
        parsed_section_repo: InMemoryParsedSectionRepository,
        ontology_mapper: OntologyMapper,
        prompt_registry: PromptTemplateRegistry,
        doc_type_detector: DocTypeDetector,
        metadata_extractor: MetadataExtractor,
        doc_id_generator: DocIdGenerator,
        llm_card_adapter: LLMCardAdapter,
        precheck: CardValidationPrecheck,
        confidence_calculator: ConfidenceCalculator,
        source_lifecycle: SourceLifecycleService,
        artifact_storage: ArtifactStorage,
        event_bus: EventBus | None = None,
        audit_service: AuditService | None = None,
        metrics: MetricsRegistry | None = None,
        confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
        taxonomy_registry: TaxonomyRegistry | None = None,
        # SETUP-05 crash-safety: коллбек, который вызывается после каждой
        # обработанной секции. В prod-DI wired на persister.save() — snapshot
        # на disk, чтобы аварийная остановка не потеряла часы LLM-работы.
        on_section_progress: object | None = None,
    ) -> None:
        self._jobs = job_repo
        self._sections = job_section_repo
        self._card_registry = card_registry
        self._source_links = source_link_repo
        self._reports = report_repo
        self._parsed_sections = parsed_section_repo
        self._ontology = ontology_mapper
        self._prompts = prompt_registry
        self._doc_type_detector = doc_type_detector
        self._metadata_extractor = metadata_extractor
        self._doc_id_gen = doc_id_generator
        self._llm = llm_card_adapter
        self._precheck = precheck
        self._confidence = confidence_calculator
        self._lifecycle = source_lifecycle
        self._storage = artifact_storage
        self._bus = event_bus
        self._audit = audit_service
        self._metrics = metrics
        self._threshold = confidence_threshold
        # SETUP-12 wiring: при llm-mode инжектируем TaxonomyRegistry,
        # чтобы добавлять taxonomy_path / primary_l0 в card front_matter.
        # None означает rule_based mode — front_matter без taxonomy полей.
        self._taxonomy_registry = taxonomy_registry
        self._on_section_progress = on_section_progress

    def _emit_progress(self) -> None:
        """Best-effort persist snapshot. Не бросает при сбое."""
        cb = self._on_section_progress
        if cb is None:
            return
        try:
            cb()  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            logger.debug(
                "on_section_progress callback failed", exc_info=True
            )

    # ============================================================
    # Public API
    # ============================================================

    def create_job(
        self,
        *,
        setup_job_id: str,
        requested_by: str,
        section_ids: list[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> RAGCardGenerationJob:
        """Создаёт RAGCardGenerationJob поверх eligible parsed sections."""
        active = self._jobs.get_active_for_setup_job(setup_job_id)
        if active is not None:
            raise RAGCardGenerationAlreadyRunningError(setup_job_id, active.generation_job_id)

        eligible = self._eligible_sections(setup_job_id, requested_ids=section_ids)
        if not eligible:
            raise NoSectionsReadyError(setup_job_id)

        now = _now()
        gen_id = _gen_id("gen")
        job = RAGCardGenerationJob(
            generation_job_id=gen_id,
            setup_job_id=setup_job_id,
            requested_by=requested_by,
            status=RAGCardGenerationJobStatus.CREATED,
            total_sections=len(eligible),
            created_at=now,
            updated_at=now,
            config=config or {},
        )
        try:
            self._jobs.create(job)
        except DuplicateRAGCardGenerationJobError as exc:
            raise RAGCardGenerationAlreadyRunningError(setup_job_id, exc.generation_job_id) from exc

        for section in eligible:
            self._sections.add(
                RAGCardGenerationJobSection(
                    generation_job_section_id=_gen_id("gjs"),
                    generation_job_id=gen_id,
                    section_id=section.section_id,
                    source_document_id=section.source_document_id,
                    status=RAGCardGenerationJobSectionStatus.PENDING,
                )
            )

        self._emit(
            RAGCardGenerationJobCreatedEvent(
                event_id=_gen_id("evt"),
                generation_job_id=gen_id,
                setup_job_id=setup_job_id,
                occurred_at=now,
                total_sections=len(eligible),
                requested_by=requested_by,
            )
        )
        self._audit_record(
            actor_id=requested_by,
            action=AuditAction.RAG_CARD_GENERATION_TRIGGERED,
            target_type="rag_card_generation_job",
            target_id=gen_id,
            setup_job_id=setup_job_id,
            payload={
                "total_sections": len(eligible),
                "section_ids": [s.section_id for s in eligible],
            },
        )
        return job

    def run(self, generation_job_id: str) -> RAGCardGenerationJob:
        """Синхронный запуск pipeline. Возвращает финальное состояние job."""
        job = self._jobs.get(generation_job_id)

        if job.status == RAGCardGenerationJobStatus.CREATED:
            job.transition_to(RAGCardGenerationJobStatus.QUEUED)
        if job.status == RAGCardGenerationJobStatus.QUEUED:
            job.transition_to(RAGCardGenerationJobStatus.RUNNING)

        started_at = _now()
        job.started_at = started_at
        job.updated_at = started_at
        self._jobs.update(job)

        self._emit(
            RAGCardGenerationJobStartedEvent(
                event_id=_gen_id("evt"),
                generation_job_id=generation_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=started_at,
                total_sections=job.total_sections,
            )
        )

        # T-S05-040: structured log — job started.
        logger.info(
            "rag_card_generation_job_started",
            extra={
                "generation_job_id": generation_job_id,
                "setup_job_id": job.setup_job_id,
                "total_sections": job.total_sections,
                "requested_by": job.requested_by,
            },
        )

        generated = 0
        failed = 0
        review_required = 0
        cards_by_type: Counter[str] = Counter()
        errors: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        affected_documents: set[str] = set()

        # SETUP-05 crash-safety + resume: пропускаем секции, которые уже
        # обработаны в предыдущем прогоне (COMPLETED или FAILED). Учитываем
        # их в counters, чтобы job.processed_sections отражал реальность.
        for js in self._sections.list_for_job(generation_job_id):
            # Resume-skip
            if js.status == RAGCardGenerationJobSectionStatus.COMPLETED:
                generated += 1
                if js.target_doc_type:
                    cards_by_type[js.target_doc_type] += 1
                affected_documents.add(js.source_document_id)
                continue
            if js.status == RAGCardGenerationJobSectionStatus.FAILED:
                failed += 1
                if js.error_code is not None:
                    errors.append(
                        {
                            "section_id": js.section_id,
                            "code": js.error_code.value,
                            "message": js.error_message or "",
                        }
                    )
                affected_documents.add(js.source_document_id)
                continue

            outcome = self._process_section(job=job, job_section=js)
            affected_documents.add(js.source_document_id)
            if outcome.status == RAGCardGenerationJobSectionStatus.COMPLETED:
                generated += 1
                if outcome.doc_type:
                    cards_by_type[outcome.doc_type] += 1
                if outcome.review_required:
                    review_required += 1
            elif outcome.status == RAGCardGenerationJobSectionStatus.FAILED:
                failed += 1
                latest = self._sections.get(js.generation_job_section_id)
                if latest.error_code is not None:
                    errors.append(
                        {
                            "section_id": latest.section_id,
                            "code": latest.error_code.value,
                            "message": latest.error_message or "",
                        }
                    )

            # SETUP-05 UX: incremental progress + crash-safety.
            try:
                job_live = self._jobs.get(generation_job_id)
                job_live.processed_sections = generated + failed
                job_live.generated_cards = generated
                job_live.failed_sections = failed
                job_live.review_required_cards = review_required
                job_live.updated_at = _now()
                self._jobs.update(job_live)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Failed to update card gen job live counters",
                    exc_info=True,
                )
            # Persist snapshot: аварийная остановка не потеряет прогресс.
            self._emit_progress()

        finished_at = _now()
        duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)

        # Determine terminal status.
        job = self._jobs.get(generation_job_id)
        if failed == 0 and generated == job.total_sections:
            target = RAGCardGenerationJobStatus.COMPLETED
        elif generated == 0:
            target = RAGCardGenerationJobStatus.FAILED
        else:
            target = RAGCardGenerationJobStatus.PARTIAL_SUCCESS

        job.transition_to(target)
        job.processed_sections = generated + failed
        job.generated_cards = generated
        job.failed_sections = failed
        job.review_required_cards = review_required
        job.finished_at = finished_at
        job.updated_at = finished_at
        if target == RAGCardGenerationJobStatus.FAILED:
            job.error_code = RAGCardGenerationErrorCode.INVALID_LLM_OUTPUT
            job.error_message = f"All {job.total_sections} sections failed card generation"
        self._jobs.update(job)

        # Финальный CardGenerationReport.
        self._reports.save(
            CardGenerationReportDTO(
                generation_report_id=_gen_id("rep"),
                generation_job_id=generation_job_id,
                status=target,
                summary=CardGenerationSummary(
                    total_sections=job.total_sections,
                    processed_sections=job.processed_sections,
                    generated_cards=generated,
                    failed_sections=failed,
                    review_required_cards=review_required,
                    cards_by_type=dict(cards_by_type),
                ),
                errors=errors,
                warnings=warnings,
                created_at=finished_at,
            )
        )

        # Финальный SourceDocument lifecycle update — RAG_CARDS_GENERATED для
        # каждого затронутого документа, чьи карточки хотя бы частично созданы.
        if generated > 0:
            for src_id in affected_documents:
                self._safe_status_update(
                    source_document_id=src_id,
                    new_status=SourceDocumentStatus.RAG_CARDS_GENERATED,
                    event_id=f"{generation_job_id}:done:{src_id}",
                    reason=f"RAG cards generated via job {generation_job_id}",
                )

        # Финальный event.
        if target == RAGCardGenerationJobStatus.COMPLETED:
            self._emit(
                RAGCardGenerationJobCompletedEvent(
                    event_id=_gen_id("evt"),
                    generation_job_id=generation_job_id,
                    setup_job_id=job.setup_job_id,
                    occurred_at=finished_at,
                    total_sections=job.total_sections,
                    generated_cards=generated,
                    failed_sections=failed,
                    review_required_cards=review_required,
                    duration_ms=duration_ms,
                )
            )
        elif target == RAGCardGenerationJobStatus.PARTIAL_SUCCESS:
            self._emit(
                RAGCardGenerationJobPartialSuccessEvent(
                    event_id=_gen_id("evt"),
                    generation_job_id=generation_job_id,
                    setup_job_id=job.setup_job_id,
                    occurred_at=finished_at,
                    generated_cards=generated,
                    failed_sections=failed,
                    review_required_cards=review_required,
                )
            )
        else:
            self._emit(
                RAGCardGenerationJobFailedEvent(
                    event_id=_gen_id("evt"),
                    generation_job_id=generation_job_id,
                    setup_job_id=job.setup_job_id,
                    occurred_at=finished_at,
                    error_code=(
                        job.error_code.value
                        if job.error_code
                        else RAGCardGenerationErrorCode.INVALID_LLM_OUTPUT.value
                    ),
                    reason=job.error_message or "Generation failed",
                )
            )

        self._inc(
            "rag_card_generation_jobs_total",
            labels={"outcome": target.value},
            help_text="RAGCardGenerationJob terminal outcomes",
        )

        # T-S05-040: structured log — job finished.
        logger.info(
            "rag_card_generation_job_finished",
            extra={
                "generation_job_id": generation_job_id,
                "setup_job_id": job.setup_job_id,
                "total_sections": job.total_sections,
                "generated_cards": generated,
                "failed_sections": failed,
                "review_required_cards": review_required,
                "duration_ms": duration_ms,
                "outcome": target.value,
            },
        )
        return job

    # ============================================================
    # Per-section pipeline
    # ============================================================

    def _process_section(
        self,
        *,
        job: RAGCardGenerationJob,
        job_section: RAGCardGenerationJobSection,
    ) -> _SectionOutcome:
        # Загружаем ParsedSection из репо.
        try:
            section = self._parsed_sections.get(job_section.section_id)
        except Exception as exc:  # noqa: BLE001 — typed errors
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=RAGCardGenerationErrorCode.SECTION_NOT_FOUND,
                reason=f"Section not found: {exc}",
                doc_type=None,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=None,
                doc_type=None,
                review_required=False,
            )

        # Mark PROCESSING.
        started_at = _now()
        job_section.status = RAGCardGenerationJobSectionStatus.PROCESSING
        job_section.started_at = started_at
        self._sections.update(job_section)

        # Lifecycle: document → RAG_CARDS_GENERATING.
        self._safe_status_update(
            source_document_id=section.source_document_id,
            new_status=SourceDocumentStatus.RAG_CARDS_GENERATING,
            event_id=f"{job.generation_job_id}:start:{section.source_document_id}",
            reason=f"RAG card generation started (job {job.generation_job_id})",
        )

        # 1. DocType detection.
        decision = self._doc_type_detector.detect(section)
        if decision.doc_type is None:
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=RAGCardGenerationErrorCode.INVALID_DOC_TYPE,
                reason=f"No doc_type for section_type={section.section_type.value}",
                doc_type=None,
                section=section,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=None,
                doc_type=None,
                review_required=False,
            )
        doc_type = decision.doc_type

        # 2. Metadata candidates.
        candidates = self._metadata_extractor.extract(section)

        # 3. Ontology normalization warnings (для prompt context — pass-through).
        ontology_warnings: list[OntologyWarning] = []
        ontology_values = {
            field: sorted(self._ontology.allowed_values(field))
            for field in (
                "domain",
                "task_type",
                "data_source",
                "entity_type",
                "phase",
                "agent_targets",
            )
        }

        # SETUP-12 / T-S12-051 wiring: при llm-mode дополняем section-контекст
        # taxonomy_path/primary_l0/primary_l1, чтобы LLM видел иерархическую
        # классификацию, и достаём taxonomy_path для hierarchical prompt lookup.
        # При rule_based mode taxonomy_registry=None — блок no-op.
        section_taxonomy: dict[str, Any] = {}
        if (
            self._taxonomy_registry is not None
            and section.classification_state is not None
        ):
            try:
                from fe_bot.taxonomy import build_taxonomy_section_dict

                section_taxonomy = build_taxonomy_section_dict(
                    section, registry=self._taxonomy_registry
                )
            except Exception:  # noqa: BLE001 — augmentation must stay safe.
                logger.exception(
                    "Failed to augment prompt context with taxonomy fields"
                )
        taxonomy_path = section_taxonomy.get("taxonomy_path")

        # 4. Build prompt context.
        ctx = PromptContext(
            section={
                "title": section.title,
                "section_type": section.section_type.value,
                "heading_path": section.heading_path,
                "normalized_text": section.normalized_text or section.raw_text,
                **section_taxonomy,
            },
            source_trace={
                "filename": f"src:{section.source_document_id}",
                "source_section_id": section.section_id,
            },
            ontology=ontology_values,
            metadata_schema={
                "required_fields": [
                    "doc_id",
                    "doc_type",
                    "title",
                    "source_files",
                    "source_sections",
                ],
            },
            metadata_candidates={
                "title": candidates.title,
                "retrieval_tags": candidates.retrieval_tags,
                "required_input_fields": candidates.required_input_fields,
                "output_fields": candidates.output_fields,
            },
            extras={"title": candidates.title, "doc_id": ""},
        )

        # 5. Render prompt + call LLM (or fallback).
        try:
            prompt = self._prompts.render(doc_type, ctx, taxonomy_path=taxonomy_path)
        except PromptTemplateNotFoundError as exc:
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=RAGCardGenerationErrorCode.PROMPT_TEMPLATE_NOT_FOUND,
                reason=str(exc),
                doc_type=doc_type,
                section=section,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=None,
                doc_type=doc_type,
                review_required=False,
            )

        generation_mode = str(job.config.get("generation_mode", "llm"))
        try:
            llm_result = self._llm.generate(prompt, doc_type=doc_type, mode=generation_mode)
        except LLMCardGenerationFailed as exc:
            error_code = _to_error_code(exc.error_code)
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=error_code,
                reason=exc.reason,
                doc_type=doc_type,
                section=section,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=None,
                doc_type=doc_type,
                review_required=False,
            )

        draft = llm_result.draft

        # 6. doc_id generation/normalization.
        existing_doc_ids = self._collect_existing_doc_ids(job.setup_job_id)
        try:
            assigned_doc_id = self._doc_id_gen.generate_doc_id(
                doc_type,
                candidates.title or draft.title or "unnamed",
                existing_doc_ids=existing_doc_ids,
            )
        except Exception as exc:  # noqa: BLE001
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=RAGCardGenerationErrorCode.INVALID_DOC_TYPE,
                reason=str(exc),
                doc_type=doc_type,
                section=section,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=None,
                doc_type=doc_type,
                review_required=False,
            )

        # Override draft.doc_id to deterministic value (LLM может галлюцинировать).
        draft = draft.model_copy(
            update={
                "doc_id": assigned_doc_id,
                "doc_type": doc_type,
                "source_files": draft.source_files or [f"src:{section.source_document_id}"],
                "source_sections": draft.source_sections or [section.section_id],
            }
        )

        # 7. Build metadata DTO.
        metadata = self._build_metadata(
            draft=draft,
            candidates=candidates,
            card_version="1.0",
        )

        # 7a. UX: кладём структурную позицию исходной секции в документе
        # (heading_path/title от парсера) прямо в front_matter — без этого
        # в Review/RAGCardList UI нет способа проверить, что карточка
        # действительно соответствует своему месту в структуре документа
        # (видно только opaque source_section_id).
        structural_fm = dict(metadata.front_matter)
        structural_fm["source_heading_path"] = list(section.heading_path)
        structural_fm["source_section_title"] = section.title
        metadata = metadata.model_copy(update={"front_matter": structural_fm})

        # 7b. SETUP-12 wiring: дополняем front_matter иерархическими
        # taxonomy полями (taxonomy_path / primary_l0 / classification_bitmap).
        # При rule_based mode taxonomy_registry=None — этот блок no-op.
        if (
            self._taxonomy_registry is not None
            and section.classification_state is not None
        ):
            try:
                from fe_bot.taxonomy import build_taxonomy_front_matter

                additions = build_taxonomy_front_matter(
                    section, registry=self._taxonomy_registry
                )
                if additions:
                    updated_fm = dict(metadata.front_matter)
                    updated_fm.update(additions)
                    metadata = metadata.model_copy(
                        update={"front_matter": updated_fm}
                    )
            except Exception:  # noqa: BLE001 — taxonomy augmentation
                # должен быть safe; ошибка не должна валить генерацию.
                logger.exception(
                    "Failed to augment metadata with taxonomy fields"
                )

        # 8. Precheck.
        precheck_report = self._precheck.check(draft, card_version="1.0")

        # 9. Confidence.
        # SETUP-12 / T-S12-053: parser classification penalty.
        # При llm-mode parser-orchestrator кладёт ClassificationState
        # в секцию; calculator применит penalty за unknown_at_level.
        decision_conf: ConfidenceDecision = self._confidence.calculate(
            precheck=precheck_report,
            llm_result=llm_result,
            ontology_warnings=ontology_warnings,
            parser_classification_state=section.classification_state,
        )
        review_required = self._confidence.is_review_required(
            decision_conf,
            threshold=self._threshold,
            precheck=precheck_report,
        )

        if not precheck_report.passed:
            # Precheck failed — карточка не сохраняется как usable.
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=RAGCardGenerationErrorCode.CARD_BODY_EMPTY,
                reason=(f"precheck failed: {[e['code'] for e in precheck_report.errors]}"),
                doc_type=doc_type,
                section=section,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=decision_conf.level,
                doc_type=doc_type,
                review_required=False,
            )

        # 10. Build markdown artifact.
        markdown_dto = build_markdown(metadata, draft.body_markdown)

        # 11. Save artifact bytes.
        storage_path = self._storage.upload(
            setup_job_id=job.setup_job_id,
            source_document_id=draft.doc_id,
            filename=f"{draft.doc_id}.md",
            content_type="text/markdown",
            data=markdown_dto.markdown.encode("utf-8"),
        )

        # 12. Build & save RAGCard.
        card_status = (
            CardStatus.REVIEW_REQUIRED
            if review_required
            else CardStatus.READY_FOR_METADATA_VALIDATION
        )
        try:
            doc_type_enum = DocType(doc_type)
        except ValueError:
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=RAGCardGenerationErrorCode.INVALID_DOC_TYPE,
                reason=f"DocType enum missing value {doc_type!r}",
                doc_type=doc_type,
                section=section,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=decision_conf.level,
                doc_type=doc_type,
                review_required=False,
            )

        card = RAGCard(
            doc_id=draft.doc_id,
            doc_type=doc_type_enum,
            title=draft.title,
            version="1.0",
            status=card_status,
            front_matter=metadata.front_matter,
            body_markdown=draft.body_markdown,
            source_document_ids=[section.source_document_id],
            source_section_ids=[section.section_id],
            confidence_level=decision_conf.level.value,
            created_by="rag-card-generator",
            created_at=_now(),
            updated_at=_now(),
            setup_job_id=job.setup_job_id,
            card_version="1.0",
            markdown_artifact_id=storage_path,
            primary_source_section_id=section.section_id,
            created_by_type="service",
            created_by_id="rag_card_generation_service",
            review_required_reason=(", ".join(decision_conf.reasons) if review_required else None),
        )
        try:
            self._card_registry.save_version(card)
        except CardAlreadyExistsError as exc:
            self._fail_section(
                job=job,
                job_section=job_section,
                error_code=RAGCardGenerationErrorCode.DOC_ID_CONFLICT,
                reason=str(exc),
                doc_type=doc_type,
                section=section,
            )
            return _SectionOutcome(
                status=RAGCardGenerationJobSectionStatus.FAILED,
                confidence=decision_conf.level,
                doc_type=doc_type,
                review_required=False,
            )

        self._card_registry.save_metadata(metadata)
        self._card_registry.attach_artifact(
            doc_id=draft.doc_id,
            card_version="1.0",
            artifact_id=storage_path,
            artifact_type="markdown",
        )

        # 13. Source lineage link (parsed_section → rag_card).
        link = RAGCardSourceLinkDTO(
            source_link_id=_gen_id("lnk"),
            doc_id=draft.doc_id,
            card_version="1.0",
            source_document_id=section.source_document_id,
            source_section_id=section.section_id,
            relation_type=LineageRelationType.GENERATED_FROM,
            created_at=_now(),
        )
        self._source_links.link(link)
        with contextlib.suppress(Exception):
            self._lifecycle.link_artifact(
                source_document_id=section.source_document_id,
                target_type=LineageTargetType.RAG_CARD,
                target_id=draft.doc_id,
                relation_type=LineageRelationType.GENERATED_FROM,
                event_id=f"{job.generation_job_id}:lineage:{draft.doc_id}",
                created_by_service="rag_card_generation_service",
                metadata={
                    "generation_job_id": job.generation_job_id,
                    "card_version": "1.0",
                },
            )

        # 14. Processing log INFO.
        finished_at = _now()
        duration_ms = max(int((finished_at - started_at).total_seconds() * 1000), 0)
        self._lifecycle.append_processing_log(
            source_document_id=section.source_document_id,
            setup_job_id=job.setup_job_id,
            step=ProcessingLogStep.RAG_CARD_GENERATION,
            message=(f"Generated RAG card {draft.doc_id} for section {section.section_id}"),
            event_id=f"{job.generation_job_id}:log:{section.section_id}",
            level=ProcessingLogLevel.INFO,
            payload={
                "generation_job_id": job.generation_job_id,
                "doc_id": draft.doc_id,
                "doc_type": doc_type,
                "confidence_level": decision_conf.level.value,
                "review_required": review_required,
                "duration_ms": duration_ms,
                "attempts": llm_result.attempts,
                "used_fallback": llm_result.used_fallback,
                "model": llm_result.model,
            },
        )

        # 15. Update job_section.
        job_section.status = RAGCardGenerationJobSectionStatus.COMPLETED
        job_section.target_doc_type = doc_type
        job_section.generated_doc_id = draft.doc_id
        job_section.confidence_level = decision_conf.level
        job_section.finished_at = finished_at
        job_section.duration_ms = duration_ms
        self._sections.update(job_section)

        # 16. Events.
        self._emit(
            RAGCardGeneratedEvent(
                event_id=_gen_id("evt"),
                generation_job_id=job.generation_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=finished_at,
                section_id=section.section_id,
                doc_id=draft.doc_id,
                doc_type=doc_type,
                card_version="1.0",
                confidence_level=decision_conf.level.value,
            )
        )
        if review_required:
            self._emit(
                RAGCardReviewRequiredEvent(
                    event_id=_gen_id("evt"),
                    generation_job_id=job.generation_job_id,
                    setup_job_id=job.setup_job_id,
                    occurred_at=finished_at,
                    section_id=section.section_id,
                    doc_id=draft.doc_id,
                    reasons=list(decision_conf.reasons),
                )
            )
            self._audit_record(
                actor_id=job.requested_by,
                action=AuditAction.RAG_CARD_REVIEW_REQUIRED,
                target_type="rag_card",
                target_id=draft.doc_id,
                setup_job_id=job.setup_job_id,
                payload={
                    "generation_job_id": job.generation_job_id,
                    "reasons": list(decision_conf.reasons),
                    "confidence_level": decision_conf.level.value,
                },
            )

        # Audit: card generated (per card).
        self._audit_record(
            actor_id=job.requested_by,
            action=AuditAction.RAG_CARD_GENERATED,
            target_type="rag_card",
            target_id=draft.doc_id,
            setup_job_id=job.setup_job_id,
            payload={
                "generation_job_id": job.generation_job_id,
                "section_id": section.section_id,
                "doc_type": doc_type,
                "confidence_level": decision_conf.level.value,
                "used_fallback": llm_result.used_fallback,
            },
        )

        # 17. Metrics.
        self._inc(
            "rag_cards_generated_total",
            labels={
                "doc_type": doc_type,
                "confidence_bucket": decision_conf.level.value,
            },
            help_text="Generated RAG cards by doc_type and confidence",
        )
        self._observe(
            "rag_card_generation_duration_ms",
            value=duration_ms,
            labels={"doc_type": doc_type},
            help_text="RAG card generation duration (ms)",
        )

        # T-S05-040: structured log — per card generated.
        logger.info(
            "rag_card_generated",
            extra={
                "generation_job_id": job.generation_job_id,
                "section_id": section.section_id,
                "doc_id": draft.doc_id,
                "doc_type": doc_type,
                "prompt_template_version": str(
                    job.config.get("prompt_template_version", "v1")
                ),
                "ontology_version": str(
                    job.config.get("ontology_version", "v1")
                ),
                "llm_model": llm_result.model,
                "confidence_level": decision_conf.level.value,
                "duration_ms": duration_ms,
                "outcome": "success",
                "used_fallback": llm_result.used_fallback,
                "attempts": llm_result.attempts,
            },
        )

        return _SectionOutcome(
            status=RAGCardGenerationJobSectionStatus.COMPLETED,
            confidence=decision_conf.level,
            doc_type=doc_type,
            review_required=review_required,
        )

    # ============================================================
    # Helpers
    # ============================================================

    def _eligible_sections(
        self, setup_job_id: str, *, requested_ids: list[str] | None
    ) -> list[ParsedSection]:
        """Возвращает ParsedSection'ы готовые к card generation.

        Группируем по parsed_jobs setup_job_id'а через source_document_id'ы
        SourceRegistry'я (SETUP-03/04 lineage). Чтобы не зависеть от ParseJob
        repository здесь, используем ``SourceRegistry.list_for_job``.
        """
        documents = self._lifecycle._registry.list_for_job(setup_job_id)
        all_sections: list[ParsedSection] = []
        for doc in documents:
            sections = self._parsed_sections.list_for_document(doc.source_document_id)
            all_sections.extend(sections)
        filtered = [s for s in all_sections if s.section_status in _SECTION_READY_STATUSES]
        if requested_ids:
            requested_set = set(requested_ids)
            filtered = [s for s in filtered if s.section_id in requested_set]
        return filtered

    def _collect_existing_doc_ids(self, setup_job_id: str) -> set[str]:
        cards = self._card_registry.list_for_setup_job(setup_job_id)
        return {c.doc_id for c in cards}

    def _build_metadata(
        self,
        *,
        draft: RAGCardDraft,
        candidates: MetadataCandidates,
        card_version: str,
    ) -> RAGCardMetadataDTO:
        # Combine LLM front_matter with deterministic candidates.
        merged: dict[str, Any] = {}
        merged.update(draft.front_matter)
        merged["doc_id"] = draft.doc_id
        merged["doc_type"] = draft.doc_type
        merged["title"] = draft.title
        merged["version"] = card_version
        merged["status"] = "generated"
        merged.setdefault("source_files", list(draft.source_files))
        merged.setdefault("source_sections", list(draft.source_sections))
        if candidates.retrieval_tags and not merged.get("retrieval_tags"):
            merged["retrieval_tags"] = list(candidates.retrieval_tags)
        if candidates.required_input_fields and not merged.get("required_input_fields"):
            merged["required_input_fields"] = list(candidates.required_input_fields)
        if candidates.output_fields and not merged.get("output_fields"):
            merged["output_fields"] = list(candidates.output_fields)
        if candidates.feature_tables and not merged.get("feature_tables"):
            merged["feature_tables"] = list(candidates.feature_tables)
        return RAGCardMetadataDTO.from_front_matter_dict(merged, card_version=card_version)

    def _fail_section(
        self,
        *,
        job: RAGCardGenerationJob,
        job_section: RAGCardGenerationJobSection,
        error_code: RAGCardGenerationErrorCode,
        reason: str,
        doc_type: str | None,
        section: ParsedSection | None = None,
    ) -> None:
        finished_at = _now()
        job_section.status = RAGCardGenerationJobSectionStatus.FAILED
        if doc_type is not None:
            job_section.target_doc_type = doc_type
        job_section.finished_at = finished_at
        job_section.error_code = error_code
        job_section.error_message = reason[:4000]
        if job_section.started_at is not None:
            job_section.duration_ms = max(
                int((finished_at - job_section.started_at).total_seconds() * 1000),
                0,
            )
        self._sections.update(job_section)

        # Processing log ERROR.
        source_doc = section.source_document_id if section else job_section.source_document_id
        self._lifecycle.append_processing_log(
            source_document_id=source_doc,
            setup_job_id=job.setup_job_id,
            step=ProcessingLogStep.RAG_CARD_GENERATION,
            message=reason,
            event_id=f"{job.generation_job_id}:errlog:{job_section.generation_job_section_id}",
            level=ProcessingLogLevel.ERROR,
            error_code=error_code.value,
            payload={
                "generation_job_id": job.generation_job_id,
                "section_id": job_section.section_id,
                "doc_type": doc_type,
            },
        )
        self._emit(
            RAGCardGenerationFailedEvent(
                event_id=_gen_id("evt"),
                generation_job_id=job.generation_job_id,
                setup_job_id=job.setup_job_id,
                occurred_at=finished_at,
                section_id=job_section.section_id,
                error_code=error_code.value,
                reason=reason,
            )
        )
        self._inc(
            "rag_cards_failed_total",
            labels={"error_code": error_code.value},
            help_text="Failed RAG card generations by error_code",
        )

        # T-S05-040: structured log — per section failure.
        logger.warning(
            "rag_card_generation_failed",
            extra={
                "generation_job_id": job.generation_job_id,
                "section_id": job_section.section_id,
                "doc_type": doc_type,
                "error_code": error_code.value,
                "outcome": "failure",
            },
        )

    def _safe_status_update(
        self,
        *,
        source_document_id: str,
        new_status: SourceDocumentStatus,
        event_id: str,
        reason: str,
    ) -> None:
        # Status может быть несовместим (например, документ ещё в PARSING) —
        # это нормально, fail силент: процессинг log всё равно фиксирует факт.
        with contextlib.suppress(Exception):
            self._lifecycle.update_status(
                source_document_id=source_document_id,
                new_status=new_status,
                event_id=event_id,
                reason=reason[:255],
            )

    # ----- side-effect adapters -----

    def _emit(self, event: _BaseRAGCardGenerationEvent) -> None:
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
        target_type: str,
        target_id: str,
        setup_job_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.record(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            setup_job_id=setup_job_id,
            payload=payload or {},
        )

    def _inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        if self._metrics is None:
            return
        self._metrics.inc(name, labels=labels, help_text=help_text)

    def _observe(
        self,
        name: str,
        *,
        value: float,
        labels: dict[str, str] | None = None,
        help_text: str = "",
    ) -> None:
        if self._metrics is None:
            return
        observe = getattr(self._metrics, "observe", None)
        if observe is not None:
            observe(name, value=value, labels=labels, help_text=help_text)
        else:  # pragma: no cover
            self._metrics.inc(name, labels=labels, help_text=help_text)


# ============================================================
# Error code mapping helper
# ============================================================


def _to_error_code(raw: str) -> RAGCardGenerationErrorCode:
    """Маппинг LLMCardGenerationFailed.error_code → RAGCardGenerationErrorCode."""
    try:
        return RAGCardGenerationErrorCode(raw)
    except ValueError:
        return RAGCardGenerationErrorCode.INVALID_LLM_OUTPUT
