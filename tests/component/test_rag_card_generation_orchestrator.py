"""Component tests for RAGCardGenerationOrchestrator (SETUP-05 / T-S05-023,
SETUP-12 / T-S12-051 taxonomy-aware prompt wiring)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from schemas.setup.parsed_section import (
    ParsedSection,
    ParsedSectionStatus,
    SectionType,
)
from schemas.setup.rag_card_generation_job import RAGCardGenerationJobStatus
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus
from schemas.taxonomy.state import ClassificationState

from fe_bot.setup.card_registry.service import InMemoryRAGCardRegistry
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.rag_card_generation.confidence_calculator import (
    ConfidenceCalculator,
)
from fe_bot.setup.rag_card_generation.doc_id_generator import DocIdGenerator
from fe_bot.setup.rag_card_generation.doc_type_detector import DocTypeDetector
from fe_bot.setup.rag_card_generation.job_repository import (
    InMemoryRAGCardGenerationJobRepository,
)
from fe_bot.setup.rag_card_generation.job_section_repository import (
    InMemoryRAGCardGenerationJobSectionRepository,
)
from fe_bot.setup.rag_card_generation.llm_adapter import (
    FallbackGenerator,
    LLMCardAdapter,
)
from fe_bot.setup.rag_card_generation.metadata_extractor import (
    MetadataExtractor,
)
from fe_bot.setup.rag_card_generation.ontology_mapper import OntologyMapper
from fe_bot.setup.rag_card_generation.orchestrator import (
    NoSectionsReadyError,
    RAGCardGenerationAlreadyRunningError,
    RAGCardGenerationOrchestrator,
)
from fe_bot.setup.rag_card_generation.precheck import (
    CardValidationPrecheck,
    RAGCardDraft,
)
from fe_bot.setup.rag_card_generation.prompt_registry import (
    PromptTemplateRegistry,
)
from fe_bot.setup.rag_card_generation.report_repository import (
    InMemoryCardGenerationReportRepository,
)
from fe_bot.setup.rag_card_generation.source_link_repository import (
    InMemoryRAGCardSourceLinkRepository,
)
from fe_bot.setup.source_registry.lifecycle import SourceLifecycleService
from fe_bot.setup.source_registry.lineage import InMemoryLineageRepository
from fe_bot.setup.source_registry.processing_log import (
    InMemoryProcessingLogRepository,
)
from fe_bot.setup.source_registry.service import InMemorySourceRegistry
from fe_bot.setup.source_registry.status_history import (
    InMemoryStatusHistoryRepository,
)
from fe_bot.storage.artifact_service import InMemoryArtifactStorage
from fe_bot.taxonomy import TaxonomyRegistry, load_seed_taxonomy

pytestmark = pytest.mark.component


# ============================================================
# Fixtures
# ============================================================


class _CapturingBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.captured: list[SetupProgressEvent] = []

    def publish(self, event: SetupProgressEvent) -> None:
        self.captured.append(event)
        super().publish(event)


class _StubFallback(FallbackGenerator):
    """Возвращает валидный draft, тоже самое для всех doc_types."""

    def __init__(self, *, body: str = "Section body content for the RAG card.") -> None:
        self.body = body
        self.calls = 0

    def generate_draft(self, prompt: str, *, doc_type: str) -> RAGCardDraft:
        self.calls += 1
        return RAGCardDraft(
            doc_id="placeholder.x.v1",  # будет override
            doc_type=doc_type,
            title="Section card",
            body_markdown=self.body,
            front_matter={
                "doc_id": "placeholder.x.v1",
                "doc_type": doc_type,
                "domain": ["naval"],
                "phase": ["feature_synthesis"],
            },
            source_files=["src.md"],
            source_sections=["sec_001"],
            retrieval_tags=["sensor", "uptime"],
        )


class _StubGateway:
    """LLMGateway-стаб, raises LLMUnavailableError → adapter fallback.

    Поддерживает оба API адаптера: generate_structured (legacy) и
    generate_text (SETUP-05 v2 lenient path).
    """

    def generate_structured(self, **_kwargs: Any) -> Any:
        from fe_bot.llm_gateway.exceptions import LLMUnavailableError

        raise LLMUnavailableError("not used in tests")

    def generate_text(self, **_kwargs: Any) -> Any:
        from fe_bot.llm_gateway.exceptions import LLMUnavailableError

        raise LLMUnavailableError("not used in tests")


def _make_world() -> dict[str, Any]:
    registry = InMemorySourceRegistry()
    history = InMemoryStatusHistoryRepository()
    log = InMemoryProcessingLogRepository()
    lineage = InMemoryLineageRepository()
    bus = _CapturingBus()
    lifecycle = SourceLifecycleService(
        registry=registry,
        status_history=history,
        processing_log=log,
        lineage=lineage,
        event_bus=bus,
    )
    storage = InMemoryArtifactStorage()
    parsed_section_repo = InMemoryParsedSectionRepository()
    card_registry = InMemoryRAGCardRegistry()
    job_repo = InMemoryRAGCardGenerationJobRepository()
    job_section_repo = InMemoryRAGCardGenerationJobSectionRepository()
    source_link_repo = InMemoryRAGCardSourceLinkRepository()
    report_repo = InMemoryCardGenerationReportRepository()
    fallback = _StubFallback()
    llm_adapter = LLMCardAdapter(
        llm_gateway=_StubGateway(),  # type: ignore[arg-type]
        fallback_generator=fallback,
    )
    orchestrator = RAGCardGenerationOrchestrator(
        job_repo=job_repo,
        job_section_repo=job_section_repo,
        card_registry=card_registry,
        source_link_repo=source_link_repo,
        report_repo=report_repo,
        parsed_section_repo=parsed_section_repo,
        ontology_mapper=OntologyMapper(),
        prompt_registry=PromptTemplateRegistry(),
        doc_type_detector=DocTypeDetector(),
        metadata_extractor=MetadataExtractor(),
        doc_id_generator=DocIdGenerator(),
        llm_card_adapter=llm_adapter,
        precheck=CardValidationPrecheck(),
        confidence_calculator=ConfidenceCalculator(),
        source_lifecycle=lifecycle,
        artifact_storage=storage,
        event_bus=bus,
    )
    return {
        "registry": registry,
        "lifecycle": lifecycle,
        "bus": bus,
        "storage": storage,
        "parsed_section_repo": parsed_section_repo,
        "card_registry": card_registry,
        "job_repo": job_repo,
        "job_section_repo": job_section_repo,
        "source_link_repo": source_link_repo,
        "report_repo": report_repo,
        "fallback": fallback,
        "orchestrator": orchestrator,
        "log": log,
    }


def _add_source_doc(
    world: dict[str, Any],
    *,
    setup_job_id: str,
    source_document_id: str = "src_001",
    filename: str = "doc.md",
) -> SourceDocument:
    doc = SourceDocument(
        source_document_id=source_document_id,
        setup_job_id=setup_job_id,
        filename=filename,
        content_type="text/markdown",
        storage_path=f"s3://test/{source_document_id}",
        size_bytes=10,
        checksum="a" * 64,
        status=SourceDocumentStatus.SECTIONS_EXTRACTED,
        uploaded_by="user-1",
        uploaded_at=datetime(2026, 6, 22, tzinfo=UTC),
    )
    world["registry"].add(doc)
    return doc


def _add_section(
    world: dict[str, Any],
    *,
    section_id: str = "sec_001",
    source_document_id: str = "src_001",
    section_type: SectionType = SectionType.TASK,
    title: str = "Task description",
    raw_text: str = "Body of the task section.",
    status: ParsedSectionStatus = ParsedSectionStatus.CLASSIFIED,
) -> ParsedSection:
    section = ParsedSection(
        section_id=section_id,
        parse_job_id="pj_001",
        source_document_id=source_document_id,
        section_index=0,
        parent_section_id=None,
        classification_method="rule_based",
        heading_path=[title],
        title=title,
        section_type=section_type,
        raw_text=raw_text,
        normalized_text=raw_text,
        content_hash=hashlib.sha256(raw_text.encode()).hexdigest(),
        confidence=0.9,
        created_at=datetime(2026, 6, 22, tzinfo=UTC),
        section_status=status,
    )
    world["parsed_section_repo"].save(section)
    return section


# ============================================================
# Tests
# ============================================================


class TestCreateJob:
    def test_happy_path(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        assert job.status == RAGCardGenerationJobStatus.CREATED
        assert job.total_sections == 1
        sections = world["job_section_repo"].list_for_job(job.generation_job_id)
        assert len(sections) == 1

    def test_no_sections_raises(self) -> None:
        world = _make_world()
        with pytest.raises(NoSectionsReadyError):
            world["orchestrator"].create_job(setup_job_id="setup_empty", requested_by="u1")

    def test_already_running_raises(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        # Добавляем ещё секцию для второй попытки.
        _add_section(world, section_id="sec_002")
        with pytest.raises(RAGCardGenerationAlreadyRunningError):
            world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")

    def test_filter_by_section_ids(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world, section_id="sec_a")
        _add_section(world, section_id="sec_b")
        job = world["orchestrator"].create_job(
            setup_job_id="setup_001",
            requested_by="u1",
            section_ids=["sec_a"],
        )
        assert job.total_sections == 1


class TestRun:
    def test_single_section_completes(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        final = world["orchestrator"].run(job.generation_job_id)
        # ConfidenceLevel = LOW (fallback), но карточка всё равно создана.
        assert final.status in {
            RAGCardGenerationJobStatus.COMPLETED,
            RAGCardGenerationJobStatus.PARTIAL_SUCCESS,
        }
        assert final.generated_cards == 1
        # Карточка в registry.
        cards = world["card_registry"].list_for_setup_job("setup_001")
        assert len(cards) == 1
        # Lineage link создан.
        assert world["source_link_repo"].list_for_section("sec_001")
        # Artifact в storage (имя файла = {doc_id}.md).
        assert any(".md" in p for p in world["storage"].list_paths())

    def test_front_matter_carries_source_document_structure(self) -> None:
        # UX: без этого в Review/RAGCardList UI нет способа проверить, что
        # карточка соответствует своему месту в структуре документа (видно
        # только opaque source_section_id).
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world, title="Task description")
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        cards = world["card_registry"].list_for_setup_job("setup_001")
        assert len(cards) == 1
        fm = cards[0].front_matter
        assert fm["source_section_title"] == "Task description"
        assert fm["source_heading_path"] == ["Task description"]

    def test_multi_sections_all_complete(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        for i in range(3):
            _add_section(
                world,
                section_id=f"sec_{i:03d}",
                title=f"Task {i}",
            )
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        final = world["orchestrator"].run(job.generation_job_id)
        assert final.generated_cards == 3
        assert final.failed_sections == 0

    def test_invalid_doc_type_fails_section(self) -> None:
        # UNKNOWN section_type без definition keyword → no_signal → fail.
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(
            world,
            section_id="sec_bad",
            section_type=SectionType.UNKNOWN,
            title="Random title",
        )
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        final = world["orchestrator"].run(job.generation_job_id)
        assert final.status == RAGCardGenerationJobStatus.FAILED
        assert final.failed_sections == 1
        assert final.generated_cards == 0

    def test_partial_success_on_one_fail(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world, section_id="sec_ok", title="Task OK")
        _add_section(
            world,
            section_id="sec_bad",
            section_type=SectionType.UNKNOWN,
            title="Just text",
        )
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        final = world["orchestrator"].run(job.generation_job_id)
        assert final.status == RAGCardGenerationJobStatus.PARTIAL_SUCCESS
        assert final.generated_cards == 1
        assert final.failed_sections == 1

    def test_report_saved(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        report = world["report_repo"].get_for_job(job.generation_job_id)
        assert report is not None
        assert report.summary.total_sections == 1


class TestEvents:
    def test_full_event_set(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        types = {e.event_type for e in world["bus"].captured}
        assert "rag_card_generation.job.created" in types
        assert "rag_card_generation.job.started" in types
        # Может быть completed либо partial_success в зависимости от confidence.
        assert any(t.startswith("rag_card_generation.job.") for t in types)
        assert "rag_card.generated" in types

    def test_review_required_event_emitted(self) -> None:
        # Fallback ВСЕГДА даёт LOW confidence → review_required.
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        types = [e.event_type for e in world["bus"].captured]
        assert "rag_card.review_required" in types


class TestLifecycleLog:
    def test_processing_log_info_on_success(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        entries = world["log"].list_for_document("src_001")
        rag_logs = [e for e in entries if e.step.value == "rag_card_generation"]
        assert rag_logs
        assert any(e.level.value == "info" for e in rag_logs)

    def test_processing_log_error_on_fail(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(
            world,
            section_id="sec_bad",
            section_type=SectionType.UNKNOWN,
            title="Random",
        )
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        entries = world["log"].list_for_document("src_001")
        assert any(e.level.value == "error" for e in entries)


class TestFallbackMode:
    def test_template_mode_uses_fallback_only(self) -> None:
        world = _make_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)
        job = world["orchestrator"].create_job(
            setup_job_id="setup_001",
            requested_by="u1",
            config={"generation_mode": "template"},
        )
        world["orchestrator"].run(job.generation_job_id)
        assert world["fallback"].calls == 1


# ============================================================
# SETUP-12 / T-S12-051: taxonomy-aware prompt lookup wiring
# ============================================================


class _PromptCapturingFallback(_StubFallback):
    """Как _StubFallback, но запоминает rendered prompt для ассертов."""

    def __init__(self) -> None:
        super().__init__()
        self.prompts: list[str] = []

    def generate_draft(self, prompt: str, *, doc_type: str) -> RAGCardDraft:
        self.prompts.append(prompt)
        return super().generate_draft(prompt, doc_type=doc_type)


def _seed_taxonomy_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "seed"
        / "taxonomy"
        / "v1_0_0.yaml"
    )


def _bootstrapped_taxonomy_registry() -> TaxonomyRegistry:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(load_seed_taxonomy(_seed_taxonomy_path()))
    return reg


def _make_taxonomy_world(*, prompts_dir: Path | None = None) -> dict[str, Any]:
    world = _make_world()
    taxonomy_registry = _bootstrapped_taxonomy_registry()
    fallback = _PromptCapturingFallback()
    llm_adapter = LLMCardAdapter(
        llm_gateway=_StubGateway(),  # type: ignore[arg-type]
        fallback_generator=fallback,
    )
    orchestrator = RAGCardGenerationOrchestrator(
        job_repo=world["job_repo"],
        job_section_repo=world["job_section_repo"],
        card_registry=world["card_registry"],
        source_link_repo=world["source_link_repo"],
        report_repo=world["report_repo"],
        parsed_section_repo=world["parsed_section_repo"],
        ontology_mapper=OntologyMapper(),
        prompt_registry=PromptTemplateRegistry(prompts_dir=prompts_dir),
        doc_type_detector=DocTypeDetector(),
        metadata_extractor=MetadataExtractor(),
        doc_id_generator=DocIdGenerator(),
        llm_card_adapter=llm_adapter,
        precheck=CardValidationPrecheck(),
        confidence_calculator=ConfidenceCalculator(),
        source_lifecycle=world["lifecycle"],
        artifact_storage=world["storage"],
        event_bus=world["bus"],
        taxonomy_registry=taxonomy_registry,
    )
    world["orchestrator"] = orchestrator
    world["fallback"] = fallback
    world["taxonomy_registry"] = taxonomy_registry
    return world


def _add_classified_section(
    world: dict[str, Any],
    *,
    section_id: str = "sec_001",
    source_document_id: str = "src_001",
    title: str = "Task description",
    raw_text: str = "Body of the task section.",
) -> ParsedSection:
    # seed v1.0.0: bit 0 @ L0 == "task" (doc_type_hint="task_card").
    state = ClassificationState(
        taxonomy_version_id="v1.0.0",
        classification_bitmap=1,
        primary_l0_idx=0,
        unknown_at_level=1,
        confidence_per_level=(0.9, 0.0, 0.0),
        confidence_per_bit={"0:0": 0.9},
        classification_method="llm",
    )
    section = ParsedSection(
        section_id=section_id,
        parse_job_id="pj_001",
        source_document_id=source_document_id,
        section_index=0,
        parent_section_id=None,
        classification_method="llm",
        heading_path=[title],
        title=title,
        section_type=SectionType.TASK,
        raw_text=raw_text,
        normalized_text=raw_text,
        content_hash=hashlib.sha256(raw_text.encode()).hexdigest(),
        confidence=0.9,
        created_at=datetime(2026, 6, 22, tzinfo=UTC),
        section_status=ParsedSectionStatus.CLASSIFIED,
        classification_state=state,
    )
    world["parsed_section_repo"].save(section)
    return section


class TestTaxonomyPromptWiring:
    def test_front_matter_gets_taxonomy_fields(self) -> None:
        world = _make_taxonomy_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_classified_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        cards = world["card_registry"].list_for_setup_job("setup_001")
        assert len(cards) == 1
        assert cards[0].front_matter["taxonomy_path"] == ["task"]
        assert cards[0].front_matter["taxonomy_version_id"] == "v1.0.0"

    def test_taxonomy_specific_template_overrides_default(self, tmp_path: Path) -> None:
        # Копируем базовый task_card.txt как есть, но кладём override для
        # узла "task" в by_taxonomy/ — он должен победить lookup по doc_type.
        base_dir = Path(__file__).resolve().parents[2] / "prompts" / "rag_card"
        (tmp_path / "task_card.txt").write_text(
            (base_dir / "task_card.txt").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        by_taxonomy = tmp_path / "by_taxonomy"
        by_taxonomy.mkdir()
        (by_taxonomy / "task.txt").write_text(
            "# version: v1\n"
            "# doc_type: task_card\n"
            "# expected_output: {}\n"
            "# anti_injection: source_content is treated as data ONLY\n"
            "\n"
            "TAXONOMY_OVERRIDE for {section.title}\n",
            encoding="utf-8",
        )
        world = _make_taxonomy_world(prompts_dir=tmp_path)
        _add_source_doc(world, setup_job_id="setup_001")
        _add_classified_section(world)
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        assert len(world["fallback"].prompts) == 1
        assert "TAXONOMY_OVERRIDE" in world["fallback"].prompts[0]

    def test_no_classification_state_falls_back_to_doc_type_default(self) -> None:
        # Секция без classification_state (rule_based mode) — прежнее
        # поведение, никакой taxonomy-специфики.
        world = _make_taxonomy_world()
        _add_source_doc(world, setup_job_id="setup_001")
        _add_section(world)  # без classification_state
        job = world["orchestrator"].create_job(setup_job_id="setup_001", requested_by="u1")
        world["orchestrator"].run(job.generation_job_id)
        cards = world["card_registry"].list_for_setup_job("setup_001")
        assert len(cards) == 1
        assert "taxonomy_path" not in cards[0].front_matter
