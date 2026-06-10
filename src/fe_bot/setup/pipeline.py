"""Setup pipeline (T-S01-023, расширен в T-S01-028, T-S01-032).

Тонкая обёртка над сервисами parser + card_generator + orchestrator +
validation + chunking/embedding/indexing.

В S3..S5 реализованы шаги:
- parsing → sections_extracted
- rag_cards_generating (cards сохраняются в Card Registry)
- metadata_validating
- review_required (если есть warnings/errors)
- chunking → embedding → indexing (если карточки прошли validation чисто)

В MVP запуск синхронный (внутри одного вызова /run). PostgreSQL checkpointer
и LangGraph-обёртка — T-S01-INF-002 + позднее.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field

from schemas.rag.rag_card import CardStatus
from schemas.rag.vector_index import VectorIndex, VectorIndexStatus
from schemas.setup.parsed_section import ParsedSection
from schemas.setup.rag_setup_job import SetupJobStatus

from fe_bot.setup.card_generator.service import (
    RAGCardGenerator,
    RAGCardGeneratorResult,
)
from fe_bot.setup.card_registry.service import (
    CardAlreadyExistsError,
    RAGCardRegistry,
)
from fe_bot.setup.events import SetupProgressEvent
from fe_bot.setup.metadata_validation.service import MetadataValidationService
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.parser.exceptions import ParserError
from fe_bot.setup.parser.service import DocumentParserService
from fe_bot.setup.source_registry.service import SourceRegistry
from fe_bot.vector_index.service import VectorIndexerService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineResult:
    """Сводка прогона pipeline для UI / processing report."""

    setup_job_id: str
    final_status: SetupJobStatus
    documents_total: int
    documents_parsed: int
    documents_failed: int
    sections_extracted: int
    cards_generated: int
    cards_review_required: int
    cards_used_fallback: int
    cards_metadata_validated: int = 0
    validation_warnings: int = 0
    validation_failed: int = 0
    # S5: chunking/embedding/indexing
    cards_approved_auto: int = 0
    chunks_total: int = 0
    chunks_indexed: int = 0
    chunks_failed: int = 0
    vector_index: VectorIndex | None = None
    errors: list[str] = field(default_factory=list)


class SetupPipeline:
    """Запускает scope S3+S4 (parse + cards + validation) для одного setup job."""

    def __init__(
        self,
        *,
        orchestrator: SetupOrchestrator,
        parser: DocumentParserService,
        card_generator: RAGCardGenerator,
        source_registry: SourceRegistry,
        card_registry: RAGCardRegistry,
        metadata_validation: MetadataValidationService,
        vector_indexer: VectorIndexerService | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._parser = parser
        self._card_generator = card_generator
        self._registry = source_registry
        self._card_registry = card_registry
        self._metadata_validation = metadata_validation
        self._vector_indexer = vector_indexer

    def run(self, setup_job_id: str) -> PipelineResult:
        """Прогоняет S3-шаги синхронно. Возвращает PipelineResult."""
        job = self._orchestrator.get_job(setup_job_id)
        if job.status != SetupJobStatus.FILES_UPLOADED:
            raise PipelineError(
                f"Pipeline can only run from FILES_UPLOADED, current={job.status.value}"
            )

        documents = self._registry.list_for_job(setup_job_id)
        result = PipelineResult(
            setup_job_id=setup_job_id,
            final_status=job.status,
            documents_total=len(documents),
            documents_parsed=0,
            documents_failed=0,
            sections_extracted=0,
            cards_generated=0,
            cards_review_required=0,
            cards_used_fallback=0,
        )

        if not documents:
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.FAILED,
                message="No documents uploaded — cannot run pipeline",
            )
            result.final_status = SetupJobStatus.FAILED
            result.errors.append("NO_DOCUMENTS")
            return result

        # ---------- Step 1: parsing → sections_extracted ----------
        self._orchestrator.advance(
            setup_job_id,
            SetupJobStatus.PARSING,
            message=f"Parsing {len(documents)} document(s)",
        )

        sections: list[ParsedSection] = []
        for document in documents:
            try:
                doc_sections = self._parser.parse(document)
                sections.extend(doc_sections)
                result.documents_parsed += 1
                result.sections_extracted += len(doc_sections)
            except ParserError as exc:
                result.documents_failed += 1
                result.errors.append(f"PARSE[{document.filename}]: {exc}")
                logger.warning(
                    "Document parse failed for %s: %s", document.source_document_id, exc
                )

        if result.documents_parsed == 0:
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.FAILED,
                message="All documents failed to parse",
                metrics={"documents_failed": result.documents_failed},
            )
            result.final_status = SetupJobStatus.FAILED
            return result

        self._orchestrator.advance(
            setup_job_id,
            SetupJobStatus.SECTIONS_EXTRACTED,
            message=f"Extracted {result.sections_extracted} section(s)",
            metrics={
                "sections_total": result.sections_extracted,
                "documents_parsed": result.documents_parsed,
                "documents_failed": result.documents_failed,
            },
        )

        # ---------- Step 2: rag_cards_generating ----------
        self._orchestrator.advance(
            setup_job_id,
            SetupJobStatus.RAG_CARDS_GENERATING,
            message=f"Generating RAG cards for {result.sections_extracted} sections",
        )

        generated = self._safe_generate_cards(sections, result, setup_job_id)
        result.cards_generated = len(generated)
        result.cards_review_required = sum(
            1 for r in generated if r.card.status.value == "review_required"
        )
        result.cards_used_fallback = sum(1 for r in generated if r.used_fallback)

        if result.cards_generated == 0:
            # Все генерации упали и fallback не настроен/тоже упал.
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.FAILED,
                message="No cards could be generated",
            )
            result.final_status = SetupJobStatus.FAILED
            return result

        # Сохраняем сгенерированные карточки в RAG Card Registry.
        self._persist_generated_cards(generated, setup_job_id, result)

        # ---------- Step 3: metadata_validating (T-S01-028) ----------
        self._orchestrator.advance(
            setup_job_id,
            SetupJobStatus.METADATA_VALIDATING,
            message=f"Validating metadata for {result.cards_generated} card(s)",
        )

        validation_batch = self._metadata_validation.validate_for_job(setup_job_id)
        result.cards_metadata_validated = validation_batch.passed
        result.validation_warnings = validation_batch.warnings
        result.validation_failed = validation_batch.failed
        result.cards_review_required = max(
            result.cards_review_required, validation_batch.review_required
        )

        # ---------- Step 4: review_gate ----------
        if validation_batch.review_required > 0:
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.REVIEW_REQUIRED,
                message=(
                    f"{validation_batch.review_required} card(s) require human review "
                    f"({validation_batch.warnings} warnings, {validation_batch.failed} failed)"
                ),
                metrics={
                    "review_required": validation_batch.review_required,
                    "warnings": validation_batch.warnings,
                    "failed": validation_batch.failed,
                },
            )
            result.final_status = SetupJobStatus.REVIEW_REQUIRED
            return result

        # ---------- Steps 5–7 (T-S01-032): chunking → embedding → indexing ----------
        # Auto-approve чистых карточек: metadata_validated → approved.
        result.cards_approved_auto = self._auto_approve_validated_cards(setup_job_id)

        if self._vector_indexer is None:
            # Indexing-сервис не настроен (S5 не активен) — останавливаемся.
            result.final_status = SetupJobStatus.METADATA_VALIDATING
            return result

        self._run_indexing_pipeline(setup_job_id, result)
        return result

    def _auto_approve_validated_cards(self, setup_job_id: str) -> int:
        """metadata_validated → approved для чистых карточек."""
        records = self._card_registry.list_for_job(
            setup_job_id, status_in=frozenset({CardStatus.METADATA_VALIDATED})
        )
        for rec in records:
            updated = rec.card.model_copy(update={"status": CardStatus.APPROVED})
            self._card_registry.update(
                rec.card.doc_id, card=updated, note="auto-approved (no validation issues)"
            )
        return len(records)

    def _run_indexing_pipeline(
        self, setup_job_id: str, result: PipelineResult
    ) -> None:
        """T-S01-032: chunking → embedding → indexing."""
        assert self._vector_indexer is not None
        approved_records = self._card_registry.list_for_job(
            setup_job_id, status_in=frozenset({CardStatus.APPROVED})
        )
        if not approved_records:
            # Нет approved карточек для индексации (например, все деpresetted).
            result.final_status = SetupJobStatus.METADATA_VALIDATING
            return

        # Step 5: chunking → embedding → indexing (один проход)
        self._orchestrator.advance(
            setup_job_id,
            SetupJobStatus.CHUNKING,
            message=f"Chunking {len(approved_records)} approved card(s)",
        )

        pairs = [(r.card, r.metadata) for r in approved_records]
        # Note: chunking + embedding + indexing идут как один шаг в VectorIndexerService.
        # Мы эмитим статусы вручную для UI/progress.
        try:
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.EMBEDDING,
                message=f"Building embeddings for {len(approved_records)} card(s)",
            )
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.INDEXING,
                message="Upserting to vector index",
            )
            index_result = self._vector_indexer.index_cards(pairs)
        except Exception as exc:
            logger.error("Indexing pipeline crashed: %s", exc)
            result.errors.append(f"INDEXING_CRASHED: {type(exc).__name__}: {exc}")
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.FAILED,
                message=f"Indexing crashed: {exc}",
            )
            result.final_status = SetupJobStatus.FAILED
            return

        result.chunks_total = index_result.chunks_total
        result.chunks_indexed = index_result.chunks_indexed
        result.chunks_failed = index_result.chunks_failed
        result.vector_index = index_result.vector_index
        result.errors.extend(index_result.errors)

        if (
            index_result.vector_index is None
            or index_result.vector_index.status == VectorIndexStatus.FAILED
        ):
            self._orchestrator.advance(
                setup_job_id,
                SetupJobStatus.FAILED,
                message=(
                    f"Indexing failed: {index_result.chunks_failed}/"
                    f"{index_result.chunks_total} chunks failed"
                ),
                metrics={
                    "chunks_total": index_result.chunks_total,
                    "chunks_indexed": index_result.chunks_indexed,
                    "chunks_failed": index_result.chunks_failed,
                },
            )
            result.final_status = SetupJobStatus.FAILED
            return

        # Перевести карточки в CHUNKED → EMBEDDED → INDEXED (lifecycle).
        for rec in approved_records:
            for target in (
                CardStatus.CHUNKED,
                CardStatus.EMBEDDED,
                CardStatus.INDEXED,
            ):
                current = self._card_registry.get(rec.card.doc_id).card
                if current.can_transition_to(target):
                    updated = current.model_copy(update={"status": target})
                    self._card_registry.update(
                        rec.card.doc_id,
                        card=updated,
                        note=f"transitioned to {target.value} via S5 pipeline",
                    )

        # Pipeline дошёл до конца S5 — финальный статус INDEXING (S6 переведёт
        # в RETRIEVAL_TESTING + PUBLISHING + READY).
        result.final_status = SetupJobStatus.INDEXING

    def _persist_generated_cards(
        self,
        generated: list[RAGCardGeneratorResult],
        setup_job_id: str,
        result: PipelineResult,
    ) -> None:
        """Сохраняет сгенерированные карточки в registry.

        Дубликаты по doc_id (например, при rerun без force_regenerate) — пропускаются
        с записью в result.errors. Это safety-net; реальные дедуп-стратегии — S5+.
        """
        for gen in generated:
            try:
                self._card_registry.add(
                    setup_job_id=setup_job_id,
                    card=gen.card,
                    metadata=gen.metadata,
                    section_id=gen.card.source_section_ids[0]
                    if gen.card.source_section_ids
                    else None,
                )
            except CardAlreadyExistsError as exc:
                # Дубликат — пропускаем, но фиксируем.
                result.errors.append(f"DUP[{exc.doc_id}]: already in registry")
                logger.warning("Card %s already exists in registry", exc.doc_id)
            except Exception as exc:
                result.errors.append(
                    f"REGISTRY[{gen.card.doc_id}]: {type(exc).__name__}: {exc}"
                )
                logger.warning(
                    "Failed to persist card %s: %s", gen.card.doc_id, exc
                )

    def _safe_generate_cards(
        self,
        sections: Iterable[ParsedSection],
        result: PipelineResult,
        setup_job_id: str,
    ) -> list[RAGCardGeneratorResult]:
        generated: list[RAGCardGeneratorResult] = []
        for section in sections:
            try:
                gen_result = self._card_generator.generate(section)
                generated.append(gen_result)
            except Exception as exc:
                result.errors.append(
                    f"CARD[{section.section_id}]: {type(exc).__name__}: {exc}"
                )
                logger.warning(
                    "Card generation failed for section %s: %s",
                    section.section_id,
                    exc,
                )
        return generated


class PipelineError(RuntimeError):
    """Невалидное состояние для запуска pipeline."""


def make_pipeline_started_event(setup_job_id: str, count: int) -> SetupProgressEvent:
    """Helper for tests / SSE."""
    return SetupProgressEvent(
        event_type="setup.step.started",
        setup_job_id=setup_job_id,
        step=SetupJobStatus.PARSING,
        status="in_progress",
        progress_percent=15.0,
        message=f"Pipeline started for {count} documents",
    )
