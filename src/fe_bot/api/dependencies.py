"""FastAPI dependencies: auth, orchestrator, repository.

В тестах перекрываются через `app.dependency_overrides`.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from schemas.setup.parse_job import ParserStrategy as ParserStrategyEnum
from schemas.setup.parsed_section import ParsedSection

from fe_bot.audit.service import AuditService, InMemoryAuditLog
from fe_bot.auth.permissions import Permission
from fe_bot.auth.service import (
    AuthService,
    ForbiddenError,
    Principal,
    UnauthenticatedError,
)
from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.observability.metrics import MetricsRegistry
from fe_bot.retrieval.service import RetrievalService
from fe_bot.setup.card_generator.service import (
    RAGCardFallbackGenerator,
    RAGCardGenerator,
    RAGCardGeneratorResult,
)
from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry
from fe_bot.setup.card_review.service import RAGCardReviewService
from fe_bot.setup.chunking.service import ChunkingService
from fe_bot.setup.embedding.service import EmbeddingService
from fe_bot.setup.evaluation.service import RAGEvaluationService
from fe_bot.setup.events import EventBus
from fe_bot.setup.metadata_validation.service import MetadataValidationService
from fe_bot.setup.orchestrator import SetupOrchestrator
from fe_bot.setup.parser.classifier import SectionClassifier
from fe_bot.setup.parser.document_repository import (
    InMemoryParseJobDocumentRepository,
)
from fe_bot.setup.parser.job_repository import InMemoryParseJobRepository
from fe_bot.setup.parser.orchestrator import DocumentParserOrchestrator
from fe_bot.setup.parser.registry import ParserRegistry
from fe_bot.setup.parser.report_repository import (
    InMemoryDocumentParseReportRepository,
)
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.parser.service import DocumentParserService
from fe_bot.setup.parser.strategies import (
    CSVParserStrategy,
    DOCXParserStrategy,
    JSONParserStrategy,
    MarkdownParserStrategy,
    PDFParserStrategy,
    PlainTextParserStrategy,
    XLSXParserStrategy,
)
from fe_bot.setup.pipeline import SetupPipeline
from fe_bot.setup.publish.service import (
    InMemoryKBRepository,
    KBPublishService,
)
from fe_bot.setup.repository import InMemoryJobRepository
from fe_bot.setup.source_registry.lifecycle import SourceLifecycleService
from fe_bot.setup.source_registry.lineage import InMemoryLineageRepository
from fe_bot.setup.source_registry.processing_log import (
    InMemoryProcessingLogRepository,
)
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.setup.source_registry.status_history import (
    InMemoryStatusHistoryRepository,
)
from fe_bot.setup.upload.batch_registry import InMemoryBatchRegistry
from fe_bot.setup.upload.cleanup import OrphanCleanupService
from fe_bot.setup.upload.idempotency import InMemoryIdempotencyCache
from fe_bot.setup.upload.service import DocumentUploadService
from fe_bot.storage.artifact_service import InMemoryArtifactStorage
from fe_bot.vector_index.client import InMemoryVectorIndexClient
from fe_bot.vector_index.service import VectorIndexerService

# Module-level singletons. Production replaces with proper DI container.
_auth_service = AuthService()
_job_repository = InMemoryJobRepository()
_event_bus = EventBus()
_orchestrator = SetupOrchestrator(_job_repository, _event_bus)
_artifact_storage = InMemoryArtifactStorage()
_source_registry = InMemorySourceRegistry()
_audit_log = InMemoryAuditLog()
_audit_service = AuditService(_audit_log)
_metrics = MetricsRegistry()

# SETUP-03: Source Registry repositories + lifecycle service.
# Создаём до _upload_service — он использует lifecycle для T-S03-019.
_status_history_repo = InMemoryStatusHistoryRepository()
_processing_log_repo = InMemoryProcessingLogRepository()
_lineage_repo = InMemoryLineageRepository()
_source_lifecycle = SourceLifecycleService(
    registry=_source_registry,
    status_history=_status_history_repo,
    processing_log=_processing_log_repo,
    lineage=_lineage_repo,
    event_bus=_event_bus,  # T-S03-020: source.document.* events
    audit_service=_audit_service,  # T-S03-022
    metrics=_metrics,
)

_upload_service = DocumentUploadService(
    job_repository=_job_repository,
    source_registry=_source_registry,
    artifact_storage=_artifact_storage,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_metrics,
    lifecycle=_source_lifecycle,
)
_parser_service = DocumentParserService(
    artifact_storage=_artifact_storage,
    source_registry=_source_registry,
)
# OBS-LLM-01: stats collector для UI progress bar по LLM-вызовам.
from fe_bot.observability.llm_stats import LLMStatsCollector  # noqa: E402

_llm_stats = LLMStatsCollector()
# Default 60s (LLMGateway.DEFAULT_TIMEOUT_SECONDS) оказался мал для
# классификации по дереву классификаторов (SETUP-13): после ~371
# успешно классифицированных секций реального документа один-единственный
# запрос к Ollama не уложился в 60с и уронил ошибкой весь документ
# (~2.5 часа работы) — при том, что типичная латентность на этой задаче
# ~10-25с. 180с даёт запас на редкие всплески без риска зависнуть навечно.
_llm_gateway = LLMGateway(stats_collector=_llm_stats, timeout_seconds=180.0)


def get_llm_stats() -> LLMStatsCollector:
    return _llm_stats


def _is_force_fallback() -> bool:
    """Перечисляемые truthy: 1 / true / yes / on (case-insensitive)."""
    import os

    return os.environ.get("FE_BOT_FORCE_FALLBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class _FallbackOnlyCardGenerator(RAGCardGenerator):
    """Bypass LLM entirely — used when FE_BOT_FORCE_FALLBACK is set.

    Карточки сразу попадают в review_required, но pipeline не ждёт Ollama.
    """

    def __init__(self) -> None:
        self._fallback_impl = RAGCardFallbackGenerator()

    def generate(self, section: ParsedSection) -> RAGCardGeneratorResult:
        return self._fallback_impl.generate(section)


if _is_force_fallback():
    _card_generator: RAGCardGenerator = _FallbackOnlyCardGenerator()
else:
    _card_generator = RAGCardGenerator(
        llm_gateway=_llm_gateway,
        fallback_generator=RAGCardFallbackGenerator(),
    )
_card_registry = InMemoryRAGCardRegistry()
_metadata_validation = MetadataValidationService(registry=_card_registry)
_card_review = RAGCardReviewService(registry=_card_registry)
_vector_index_client = InMemoryVectorIndexClient()
_chunking = ChunkingService()
_embedding_service = EmbeddingService(llm_gateway=_llm_gateway)
_vector_indexer = VectorIndexerService(
    chunking=_chunking,
    embedding=_embedding_service,
    index_client=_vector_index_client,
)
_pipeline = SetupPipeline(
    orchestrator=_orchestrator,
    parser=_parser_service,
    card_generator=_card_generator,
    source_registry=_source_registry,
    card_registry=_card_registry,
    metadata_validation=_metadata_validation,
    vector_indexer=_vector_indexer,
)
_retrieval_service = RetrievalService(
    embedding=_embedding_service,
    index_client=_vector_index_client,
)
_evaluation_service = RAGEvaluationService(retrieval=_retrieval_service)
_kb_repository = InMemoryKBRepository()
_kb_publish = KBPublishService(repository=_kb_repository)
# _audit_log / _audit_service / _metrics — определены раньше (нужны для DocumentUploadService).
_idempotency_cache = InMemoryIdempotencyCache()
_batch_registry = InMemoryBatchRegistry()
_orphan_cleanup = OrphanCleanupService(storage=_artifact_storage, registry=_source_registry)

# SETUP-04: parser orchestrator singletons.
_parser_registry = ParserRegistry()
_parser_registry.register(ParserStrategyEnum.MARKDOWN, MarkdownParserStrategy())
_parser_registry.register(ParserStrategyEnum.TEXT, PlainTextParserStrategy())
_parser_registry.register(ParserStrategyEnum.CSV, CSVParserStrategy())
_parser_registry.register(ParserStrategyEnum.JSON, JSONParserStrategy())
_parser_registry.register(ParserStrategyEnum.PDF_TEXT, PDFParserStrategy())
_parser_registry.register(ParserStrategyEnum.DOCX, DOCXParserStrategy())
_parser_registry.register(ParserStrategyEnum.XLSX, XLSXParserStrategy())

_parse_job_repo = InMemoryParseJobRepository()
_parse_doc_repo = InMemoryParseJobDocumentRepository()
_parsed_section_repo = InMemoryParsedSectionRepository()
_parse_report_repo = InMemoryDocumentParseReportRepository()


# SETUP-12 (T-S12-070): taxonomy registry singleton. Bootstrap из seed
# YAML лениво при первом get_taxonomy_registry() вызове. Размещён до
# _build_section_classifier, так как используется при llm-mode.
import logging as _logging_for_taxonomy  # noqa: E402

from fe_bot.taxonomy import (  # noqa: E402
    TaxonomyRegistry,
    load_seed_taxonomy,
)
from fe_bot.taxonomy.seed_loader import SeedFormatError  # noqa: E402

_logger_taxonomy = _logging_for_taxonomy.getLogger(__name__)
_taxonomy_registry: TaxonomyRegistry | None = None


def _bootstrap_taxonomy_from_seed() -> TaxonomyRegistry:
    from pathlib import Path

    reg = TaxonomyRegistry()
    seed_path = (
        Path(__file__).resolve().parents[3]
        / "seed"
        / "taxonomy"
        / "v1_0_0.yaml"
    )
    if not seed_path.exists():
        _logger_taxonomy.warning(
            "Taxonomy seed not found at %s; registry stays empty",
            seed_path,
        )
        return reg
    try:
        version = load_seed_taxonomy(seed_path)
        reg.bootstrap_from_version(version)
    except (FileNotFoundError, SeedFormatError) as exc:
        _logger_taxonomy.error(
            "Failed to bootstrap taxonomy registry from %s: %s",
            seed_path,
            exc,
        )
    return reg


def get_taxonomy_registry() -> TaxonomyRegistry:
    global _taxonomy_registry
    if _taxonomy_registry is None:
        _taxonomy_registry = _bootstrap_taxonomy_from_seed()
    return _taxonomy_registry


# SETUP-13 (ADR-HTC-09): classifier library singleton. Repo создаётся
# eagerly (как остальные module-level repo в этом файле), чтобы
# register_default_state() мог зарегистрировать его в SnapshotPersister
# до первого запроса — иначе отредактированное пользователем дерево не
# переживало бы рестарт backend'а. Seed из seed/classifier/asu_v1.txt
# заливается сразу; если снапшот на диске содержит сохранённое дерево,
# persister.load() перезапишет его поверх seed при старте.
from fe_bot.classifier.import_tree import TreeImportError  # noqa: E402
from fe_bot.classifier.tree_repository import ClassifierTreeRepository  # noqa: E402
from fe_bot.classifier.tree_service import ClassifierTreeService  # noqa: E402

_logger_classifier = _logging_for_taxonomy.getLogger(__name__)


def _bootstrap_classifier_repo() -> ClassifierTreeRepository:
    from pathlib import Path

    from fe_bot.classifier.import_tree import parse_ascii_tree

    repo = ClassifierTreeRepository()
    seed_path = Path(__file__).resolve().parents[3] / "seed" / "classifier" / "asu_v1.txt"
    if not seed_path.exists():
        _logger_classifier.warning(
            "Classifier seed not found at %s; library stays empty", seed_path
        )
        return repo
    try:
        tree = parse_ascii_tree(seed_path.read_text(encoding="utf-8"))
        repo.save(tree, make_active=True)
    except TreeImportError as exc:
        _logger_classifier.error("Failed to import classifier tree from %s: %s", seed_path, exc)
    return repo


_classifier_repo = _bootstrap_classifier_repo()
_classifier_service = ClassifierTreeService(_classifier_repo)


def get_classifier_service() -> ClassifierTreeService:
    return _classifier_service


# SETUP-13: черновик описания узла через маленькую LLM (см.
# description_generator.py) — переиспользует тот же shared _llm_gateway
# singleton, что и остальные LLM-задачи в этом файле.
from fe_bot.classifier.description_generator import (  # noqa: E402
    ClassifierDescriptionGenerator,
)

_classifier_description_generator = ClassifierDescriptionGenerator(llm_gateway=_llm_gateway)


def get_classifier_description_generator() -> ClassifierDescriptionGenerator:
    return _classifier_description_generator


# Feature flag для выбора classifier'а.
# FE_BOT_TAXONOMY_MODE ∈ {rule_based, llm}. Default — rule_based (быстро,
# без LLM). При llm используется ClassifierTreeSectionClassifier —
# многоуровневая классификация по дереву SETUP-13 (см.
# fe_bot.classifier.fragment_classifier) через реальные вызовы Ollama на
# каждом уровне дерева, поэтому это ощутимо медленнее rule_based и
# требует доступный Ollama.
#
# ADR-HTC-09: SETUP-13 (generic-depth дерево классификаторов) полностью
# заменяет SETUP-12 (30-bit bitmap taxonomy, fe_bot.taxonomy.*) — код
# SETUP-12 не удалён (можно понадобится для сверки), но больше не
# вызывается отсюда.
def _taxonomy_mode() -> str:
    import os

    return os.environ.get("FE_BOT_TAXONOMY_MODE", "rule_based").strip().lower()


def _build_section_classifier():
    if _taxonomy_mode() != "llm":
        return SectionClassifier()

    from fe_bot.classifier.fragment_classifier import FragmentClassifier
    from fe_bot.classifier.prompt_renderer import ClassifierPromptRenderer
    from fe_bot.classifier.section_classifier_adapter import (
        ClassifierTreeSectionClassifier,
    )

    fragment_classifier = FragmentClassifier(
        tree_service=_classifier_service,
        renderer=ClassifierPromptRenderer(),
        llm_gateway=_llm_gateway,
    )
    return ClassifierTreeSectionClassifier(classifier=fragment_classifier)


_section_classifier = _build_section_classifier()


# SETUP-04 crash-safety: коллбек, вызываемый после каждой
# классифицированной секции. Wired на _snapshot_persister — сохраняет
# состояние на disk. app.py устанавливает _snapshot_persister при
# lifespan startup через set_snapshot_persister().
_snapshot_persister: object | None = None


def set_snapshot_persister(persister: object | None) -> None:
    """Wire callback от app.py lifespan к parser orchestrator'у."""
    global _snapshot_persister
    _snapshot_persister = persister


def _persist_incremental_snapshot() -> None:
    p = _snapshot_persister
    if p is None:
        return
    try:
        p.save()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        # Persister сам логирует; здесь тихо игнорируем — не блочим парсинг.
        pass


_document_parser_orchestrator = DocumentParserOrchestrator(
    parse_job_repo=_parse_job_repo,
    document_repo=_parse_doc_repo,
    section_repo=_parsed_section_repo,
    report_repo=_parse_report_repo,
    parser_registry=_parser_registry,
    classifier=_section_classifier,
    source_lifecycle=_source_lifecycle,
    artifact_storage=_artifact_storage,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_metrics,
    on_section_progress=_persist_incremental_snapshot,
)

# SETUP-05 RAG Card Generation singletons (T-S05-025).
# SETUP-06 (T-S06-007..010): review repositories.
from fe_bot.setup.card_review.decision_repository import (  # noqa: E402
    InMemoryReviewDecisionRepository as _ReviewDecisionRepo,
)
from fe_bot.setup.card_review.edit_lock_repository import (  # noqa: E402
    InMemoryEditLockRepository as _EditLockRepo,
)
from fe_bot.setup.card_review.log_repository import (  # noqa: E402
    InMemoryReviewLogRepository as _ReviewLogRepo,
)
from fe_bot.setup.card_review.version_repository import (  # noqa: E402
    InMemoryRAGCardVersionRepository as _CardVersionRepo,
)
from fe_bot.setup.rag_card_generation.confidence_calculator import (  # noqa: E402
    ConfidenceCalculator as _ConfidenceCalculator,
)
from fe_bot.setup.rag_card_generation.doc_id_generator import (  # noqa: E402
    DocIdGenerator as _DocIdGenerator,
)
from fe_bot.setup.rag_card_generation.doc_type_detector import (  # noqa: E402
    DocTypeDetector as _DocTypeDetector,
)
from fe_bot.setup.rag_card_generation.job_repository import (  # noqa: E402
    InMemoryRAGCardGenerationJobRepository as _RAGJobRepo,
)
from fe_bot.setup.rag_card_generation.job_section_repository import (  # noqa: E402
    InMemoryRAGCardGenerationJobSectionRepository as _RAGSectionRepo,
)
from fe_bot.setup.rag_card_generation.llm_adapter import (  # noqa: E402
    LLMCardAdapter as _LLMCardAdapter,
)
from fe_bot.setup.rag_card_generation.metadata_extractor import (  # noqa: E402
    MetadataExtractor as _MetadataExtractor,
)
from fe_bot.setup.rag_card_generation.ontology_mapper import (  # noqa: E402
    OntologyMapper as _OntologyMapper,
)
from fe_bot.setup.rag_card_generation.orchestrator import (  # noqa: E402
    RAGCardGenerationOrchestrator as _RAGCardOrchestrator,
)
from fe_bot.setup.rag_card_generation.precheck import (  # noqa: E402
    CardValidationPrecheck as _CardValidationPrecheck,
)
from fe_bot.setup.rag_card_generation.prompt_registry import (  # noqa: E402
    PromptTemplateRegistry as _PromptTemplateRegistry,
)
from fe_bot.setup.rag_card_generation.report_repository import (  # noqa: E402
    InMemoryCardGenerationReportRepository as _CardReportRepo,
)
from fe_bot.setup.rag_card_generation.source_link_repository import (  # noqa: E402
    InMemoryRAGCardSourceLinkRepository as _RAGSourceLinkRepo,
)

_rag_card_job_repo = _RAGJobRepo()
_rag_card_section_repo = _RAGSectionRepo()
_rag_card_source_link_repo = _RAGSourceLinkRepo()
_card_generation_report_repo = _CardReportRepo()

# SETUP-06: review state.
_review_decision_repo = _ReviewDecisionRepo()
_review_log_repo = _ReviewLogRepo()
_card_version_repo = _CardVersionRepo()
_edit_lock_repo = _EditLockRepo()

# SETUP-07 (T-S07-010): validation persistence.
from fe_bot.setup.metadata_validation.metrics import (  # noqa: E402
    ValidationMetricsCollector as _ValidationMetricsCollector,
)
from fe_bot.setup.metadata_validation.report_repository import (  # noqa: E402
    InMemoryValidationReportRepository as _ValidationReportRepo,
)
from fe_bot.setup.metadata_validation.run_repository import (  # noqa: E402
    InMemoryValidationRunRepository as _ValidationRunRepo,
)

_validation_report_repo = _ValidationReportRepo()
_validation_run_repo = _ValidationRunRepo()
_validation_metrics = _ValidationMetricsCollector(metrics=_metrics)

# SETUP-08 (T-S08-010): chunking persistence + observability.
from fe_bot.setup.chunking.manifest_repository import (  # noqa: E402
    InMemoryChunkManifestRepository as _ChunkManifestRepo,
)
from fe_bot.setup.chunking.metrics import (  # noqa: E402
    ChunkingMetricsCollector as _ChunkingMetricsCollector,
)
from fe_bot.setup.chunking.orchestrator import (  # noqa: E402
    ChunkingOrchestrator as _ChunkingOrchestrator,
)

_chunk_manifest_repo = _ChunkManifestRepo()
_chunking_metrics = _ChunkingMetricsCollector(metrics=_metrics)
_chunking_orchestrator = _ChunkingOrchestrator(
    registry=_card_registry,
    chunking=_chunking,
    manifest_repo=_chunk_manifest_repo,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_chunking_metrics,
)
_ontology_mapper = _OntologyMapper()
_prompt_template_registry = _PromptTemplateRegistry()


# SETUP-12 wiring: при FE_BOT_TAXONOMY_MODE=llm используем
# TaxonomyDocTypeDetector. Иначе — legacy rule-based.
def _build_doc_type_detector():
    legacy = _DocTypeDetector()
    if _taxonomy_mode() != "llm":
        return legacy
    from fe_bot.taxonomy import TaxonomyDocTypeDetector

    return TaxonomyDocTypeDetector(
        registry=get_taxonomy_registry(),
        legacy=legacy,
    )


_doc_type_detector = _build_doc_type_detector()
_metadata_extractor = _MetadataExtractor()
_doc_id_generator = _DocIdGenerator()
_card_validation_precheck = _CardValidationPrecheck()
_confidence_calculator = _ConfidenceCalculator()
# SETUP-05 fallback: deterministic generator для template/hybrid mode и при
# недоступности LLM. Создаёт минимально валидный draft, проходящий precheck.
from fe_bot.setup.rag_card_generation.llm_adapter import (  # noqa: E402
    FallbackGenerator as _SETUP05Fallback,
)
from fe_bot.setup.rag_card_generation.precheck import (  # noqa: E402
    RAGCardDraft as _SETUP05Draft,
)


class _DefaultSETUP05Fallback(_SETUP05Fallback):
    """Stub-fallback для dev: возвращает детерминированный draft."""

    def generate_draft(self, prompt: str, *, doc_type: str) -> _SETUP05Draft:
        # Fallback всегда генерирует русский текст (см. OBS-LANG-01 / SETUP-08
        # требование «RAG карточки на русском языке»).
        return _SETUP05Draft(
            doc_id="placeholder.x.v1",
            doc_type=doc_type,
            title="Карточка, сгенерированная резервным генератором",
            body_markdown=(
                "# Карточка из резервного генератора\n\n"
                "## Описание\n\n"
                "Эта карточка создана детерминированным fallback-генератором, "
                "когда LLM (Ollama) была недоступна или дала невалидный ответ. "
                "Содержимое — заглушка; требуется human review и редактирование "
                "перед публикацией.\n\n"
                "## Источник\n\n"
                "См. поля source_files и source_sections в metadata.\n"
            ),
            front_matter={
                "doc_id": "placeholder.x.v1",
                "doc_type": doc_type,
                "domain": ["naval"],
                "phase": ["feature_synthesis"],
            },
            source_files=["src.md"],
            source_sections=["sec_001"],
            retrieval_tags=["заглушка", "резервный_генератор"],
        )


_llm_card_adapter = _LLMCardAdapter(
    llm_gateway=_llm_gateway,
    fallback_generator=_DefaultSETUP05Fallback(),
)
_rag_card_orchestrator = _RAGCardOrchestrator(
    job_repo=_rag_card_job_repo,
    job_section_repo=_rag_card_section_repo,
    card_registry=_card_registry,
    source_link_repo=_rag_card_source_link_repo,
    report_repo=_card_generation_report_repo,
    parsed_section_repo=_parsed_section_repo,
    ontology_mapper=_ontology_mapper,
    prompt_registry=_prompt_template_registry,
    doc_type_detector=_doc_type_detector,
    metadata_extractor=_metadata_extractor,
    doc_id_generator=_doc_id_generator,
    llm_card_adapter=_llm_card_adapter,
    precheck=_card_validation_precheck,
    confidence_calculator=_confidence_calculator,
    source_lifecycle=_source_lifecycle,
    artifact_storage=_artifact_storage,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_metrics,
    # SETUP-12 wiring: при llm-mode добавляем taxonomy_registry,
    # чтобы front_matter содержал taxonomy_path и связанные поля.
    taxonomy_registry=(
        get_taxonomy_registry() if _taxonomy_mode() == "llm" else None
    ),
    # SETUP-05 crash-safety: тот же persister-коллбек, что у парсера.
    # После каждой сгенерированной карточки persister.save() пишет
    # snapshot на disk — аварийная остановка не потеряет прогресс.
    on_section_progress=_persist_incremental_snapshot,
)

# SETUP-06 (T-S06-023): rewrite _card_review с полной wiring (depends on
# SETUP-05 _rag_card_orchestrator + SETUP-06 repos).
from fe_bot.setup.card_review.metrics import (  # noqa: E402
    ReviewMetricsCollector as _ReviewMetricsCollector,
)
from fe_bot.setup.card_review.readiness import (  # noqa: E402
    ReviewReadinessCalculator as _ReviewReadinessCalculator,
)

_review_readiness_calculator = _ReviewReadinessCalculator(card_registry=_card_registry)
_review_metrics_collector = _ReviewMetricsCollector(metrics=_metrics)
# SETUP-07 (T-S07-010): rewrite _metadata_validation с full wiring
# (создаётся ДО _card_review, чтобы T-S07-017 hook мог использовать его).
_metadata_validation = MetadataValidationService(
    registry=_card_registry,
    report_repo=_validation_report_repo,
    run_repo=_validation_run_repo,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_validation_metrics,
)

_card_review = RAGCardReviewService(
    registry=_card_registry,
    decision_repo=_review_decision_repo,
    log_repo=_review_log_repo,
    version_repo=_card_version_repo,
    edit_lock_repo=_edit_lock_repo,
    readiness_calculator=_review_readiness_calculator,
    event_bus=_event_bus,
    audit_service=_audit_service,
    metrics=_review_metrics_collector,
    generation_orchestrator=_rag_card_orchestrator,
    validation_service=_metadata_validation,  # T-S07-017
)


def get_auth_service() -> AuthService:
    return _auth_service


def get_orchestrator() -> SetupOrchestrator:
    return _orchestrator


def get_event_bus() -> EventBus:
    return _event_bus


def get_job_repository() -> InMemoryJobRepository:
    return _job_repository


def get_artifact_storage() -> InMemoryArtifactStorage:
    return _artifact_storage


def get_source_registry() -> InMemorySourceRegistry:
    return _source_registry


def get_upload_service() -> DocumentUploadService:
    return _upload_service


def get_parser_service() -> DocumentParserService:
    return _parser_service


def get_pipeline() -> SetupPipeline:
    return _pipeline


def get_card_registry() -> InMemoryRAGCardRegistry:
    return _card_registry


def get_metadata_validation() -> MetadataValidationService:
    return _metadata_validation


def get_card_review() -> RAGCardReviewService:
    return _card_review


def get_vector_index_client() -> InMemoryVectorIndexClient:
    return _vector_index_client


def get_vector_indexer() -> VectorIndexerService:
    return _vector_indexer


def get_retrieval_service() -> RetrievalService:
    return _retrieval_service


def get_evaluation_service() -> RAGEvaluationService:
    return _evaluation_service


def get_kb_repository() -> InMemoryKBRepository:
    return _kb_repository


def get_kb_publish_service() -> KBPublishService:
    return _kb_publish


def get_audit_log() -> InMemoryAuditLog:
    return _audit_log


def get_audit_service() -> AuditService:
    return _audit_service


def get_metrics() -> MetricsRegistry:
    return _metrics


def get_idempotency_cache() -> InMemoryIdempotencyCache:
    return _idempotency_cache


def get_batch_registry() -> InMemoryBatchRegistry:
    return _batch_registry


def get_orphan_cleanup_service() -> OrphanCleanupService:
    return _orphan_cleanup


# SETUP-03 DI factories.


def get_status_history_repo() -> InMemoryStatusHistoryRepository:
    return _status_history_repo


def get_processing_log_repo() -> InMemoryProcessingLogRepository:
    return _processing_log_repo


def get_lineage_repo() -> InMemoryLineageRepository:
    return _lineage_repo


def get_source_lifecycle() -> SourceLifecycleService:
    return _source_lifecycle


# SETUP-04 DI factories.


def get_parser_registry() -> ParserRegistry:
    return _parser_registry


def get_parse_job_repo() -> InMemoryParseJobRepository:
    return _parse_job_repo


def get_parse_document_repo() -> InMemoryParseJobDocumentRepository:
    return _parse_doc_repo


def get_parsed_section_repo() -> InMemoryParsedSectionRepository:
    return _parsed_section_repo


def get_parse_report_repo() -> InMemoryDocumentParseReportRepository:
    return _parse_report_repo


def get_document_parser_orchestrator() -> DocumentParserOrchestrator:
    return _document_parser_orchestrator


def get_principal(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_roles: str | None = Header(default=None, alias="X-Roles"),
) -> Principal:
    """Извлекает Principal из HTTP-заголовков. В MVP — простой stub."""
    try:
        return get_auth_service().authenticate(x_user_id, x_roles)
    except UnauthenticatedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


# SETUP-05 DI factories.


def get_rag_card_orchestrator() -> _RAGCardOrchestrator:
    return _rag_card_orchestrator


def get_rag_card_job_repo() -> _RAGJobRepo:
    return _rag_card_job_repo


def get_rag_card_section_repo() -> _RAGSectionRepo:
    return _rag_card_section_repo


def get_rag_card_source_link_repo() -> _RAGSourceLinkRepo:
    return _rag_card_source_link_repo


def get_card_generation_report_repo() -> _CardReportRepo:
    return _card_generation_report_repo


# SETUP-08 (T-S08-010): chunking repositories.
def get_chunk_manifest_repo() -> _ChunkManifestRepo:
    return _chunk_manifest_repo


def get_chunking_orchestrator() -> _ChunkingOrchestrator:
    return _chunking_orchestrator


# SETUP-07 (T-S07-010): validation repositories.
def get_validation_report_repo() -> _ValidationReportRepo:
    return _validation_report_repo


def get_validation_run_repo() -> _ValidationRunRepo:
    return _validation_run_repo


# SETUP-06 (T-S06-023): review repositories.
def get_review_decision_repo() -> _ReviewDecisionRepo:
    return _review_decision_repo


def get_review_log_repo() -> _ReviewLogRepo:
    return _review_log_repo


def get_card_version_repo() -> _CardVersionRepo:
    return _card_version_repo


def get_edit_lock_repo() -> _EditLockRepo:
    return _edit_lock_repo


def get_ontology_mapper() -> _OntologyMapper:
    return _ontology_mapper


def get_prompt_template_registry() -> _PromptTemplateRegistry:
    return _prompt_template_registry


def require_permission(
    permission: Permission,
) -> Callable[[Principal], Principal]:
    """Builder для зависимости, требующей конкретный permission."""

    def dependency(
        principal: Principal = Depends(get_principal),
    ) -> Principal:
        try:
            get_auth_service().require(principal, permission)
        except ForbiddenError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc
        return principal

    return dependency
