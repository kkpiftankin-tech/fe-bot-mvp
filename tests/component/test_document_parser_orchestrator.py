"""Component tests for DocumentParserOrchestrator (T-S04-020/021/022)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest
from schemas.setup.parse_job import ParseErrorCode, ParseJobStatus
from schemas.setup.parse_job import (
    ParserStrategy as ParserStrategyEnum,
)
from schemas.setup.parse_job_document import ParseJobDocumentStatus
from schemas.setup.source_document import (
    SourceDocument,
    SourceDocumentStatus,
)

from fe_bot.llm_gateway.exceptions import LLMUnavailableError
from fe_bot.setup.events import EventBus, SetupProgressEvent
from fe_bot.setup.parser.classifier import SectionClassifier
from fe_bot.setup.parser.document_repository import (
    InMemoryParseJobDocumentRepository,
)
from fe_bot.setup.parser.job_repository import InMemoryParseJobRepository
from fe_bot.setup.parser.orchestrator import (
    DocumentParserOrchestrator,
    NoParseableDocumentsError,
    ParseJobAlreadyRunningError,
)
from fe_bot.setup.parser.registry import ParserRegistry
from fe_bot.setup.parser.report_repository import (
    InMemoryDocumentParseReportRepository,
)
from fe_bot.setup.parser.section_repository import (
    InMemoryParsedSectionRepository,
)
from fe_bot.setup.parser.strategies import (
    MarkdownParserStrategy,
    PlainTextParserStrategy,
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


def _make_world(*, classifier: Any = None) -> dict[str, Any]:
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
    parser_registry = ParserRegistry()
    parser_registry.register(ParserStrategyEnum.MARKDOWN, MarkdownParserStrategy())
    parser_registry.register(ParserStrategyEnum.TEXT, PlainTextParserStrategy())

    job_repo = InMemoryParseJobRepository()
    doc_repo = InMemoryParseJobDocumentRepository()
    section_repo = InMemoryParsedSectionRepository()
    report_repo = InMemoryDocumentParseReportRepository()

    orchestrator = DocumentParserOrchestrator(
        parse_job_repo=job_repo,
        document_repo=doc_repo,
        section_repo=section_repo,
        report_repo=report_repo,
        parser_registry=parser_registry,
        classifier=classifier if classifier is not None else SectionClassifier(),
        source_lifecycle=lifecycle,
        artifact_storage=storage,
        event_bus=bus,
    )
    return {
        "registry": registry,
        "history": history,
        "log": log,
        "lineage": lineage,
        "bus": bus,
        "lifecycle": lifecycle,
        "storage": storage,
        "parser_registry": parser_registry,
        "job_repo": job_repo,
        "doc_repo": doc_repo,
        "section_repo": section_repo,
        "report_repo": report_repo,
        "orchestrator": orchestrator,
    }


def _add_source(
    *,
    world: dict[str, Any],
    setup_job_id: str,
    source_document_id: str,
    content: bytes,
    filename: str,
    content_type: str,
    initial_status: SourceDocumentStatus = SourceDocumentStatus.REGISTERED,
) -> SourceDocument:
    storage_path = world["storage"].upload(
        setup_job_id=setup_job_id,
        source_document_id=source_document_id,
        filename=filename,
        content_type=content_type,
        data=content,
    )
    checksum = hashlib.sha256(content).hexdigest()
    doc = SourceDocument(
        source_document_id=source_document_id,
        setup_job_id=setup_job_id,
        filename=filename,
        content_type=content_type,
        storage_path=storage_path,
        size_bytes=len(content),
        checksum=checksum,
        status=initial_status,
        uploaded_by="user-1",
        uploaded_at=datetime(2026, 6, 18, tzinfo=UTC),
    )
    world["registry"].add(doc)
    return doc


# ============================================================
# Tests
# ============================================================


class TestCreateParseJob:
    def test_happy_path(self) -> None:
        world = _make_world()
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_1",
            content=b"# Hello\n\nSome body text",
            filename="a.md",
            content_type="text/markdown",
        )
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        assert job.status == ParseJobStatus.CREATED
        assert job.total_documents == 1
        # ParseJobDocument создан в PENDING.
        pjds = world["doc_repo"].list_for_job(job.parse_job_id)
        assert len(pjds) == 1
        assert pjds[0].status == ParseJobDocumentStatus.PENDING

    def test_no_parseable_documents_raises(self) -> None:
        world = _make_world()
        with pytest.raises(NoParseableDocumentsError):
            world["orchestrator"].create_parse_job(setup_job_id="sj_empty", requested_by="user-1")

    def test_already_running_raises(self) -> None:
        world = _make_world()
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_1",
            content=b"# Title",
            filename="a.md",
            content_type="text/markdown",
        )
        world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_2",
            content=b"# Other",
            filename="b.md",
            content_type="text/markdown",
        )
        with pytest.raises(ParseJobAlreadyRunningError):
            world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")


class TestRun:
    def test_single_doc_completes(self) -> None:
        world = _make_world()
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_1",
            content=b"# Hello\n\nBody text here",
            filename="a.md",
            content_type="text/markdown",
        )
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        final = world["orchestrator"].run(job.parse_job_id)
        assert final.status == ParseJobStatus.COMPLETED
        assert final.processed_documents == 1
        assert final.failed_documents == 0
        assert final.total_sections >= 1

        # SourceDocument теперь SECTIONS_EXTRACTED.
        src = world["registry"].get("src_1")
        assert src.status == SourceDocumentStatus.SECTIONS_EXTRACTED

        # Lineage: relations созданы.
        relations, _ = world["lifecycle"].get_lineage("src_1")
        assert relations
        assert all(r.target_type.value == "parsed_section" for r in relations)

    def test_multi_doc_completed(self) -> None:
        world = _make_world()
        for idx in range(3):
            _add_source(
                world=world,
                setup_job_id="sj_1",
                source_document_id=f"src_{idx}",
                content=f"# Doc {idx}\n\nbody".encode(),
                filename=f"a{idx}.md",
                content_type="text/markdown",
            )
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        final = world["orchestrator"].run(job.parse_job_id)
        assert final.status == ParseJobStatus.COMPLETED
        assert final.processed_documents == 3

    def test_partial_success_on_one_fail(self) -> None:
        world = _make_world()
        # Загружаем 2 markdown'а, но "ломаем" второй — заменяем storage путь
        # на отсутствующий ключ, чтобы download'упал.
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_ok",
            content=b"# OK\n\nbody",
            filename="ok.md",
            content_type="text/markdown",
        )
        doc_bad = _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_bad",
            content=b"# Bad\n\nbody",
            filename="bad.md",
            content_type="text/markdown",
        )
        broken = doc_bad.model_copy(update={"storage_path": "s3://missing"})
        world["registry"].update(broken)

        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        final = world["orchestrator"].run(job.parse_job_id)
        assert final.status == ParseJobStatus.PARTIAL_SUCCESS
        assert final.processed_documents == 1
        assert final.failed_documents == 1
        # У упавшего документа статус — PARSE_FAILED.
        assert world["registry"].get("src_bad").status == SourceDocumentStatus.PARSE_FAILED

    def test_full_failure_all_docs(self) -> None:
        world = _make_world()
        doc = _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_only",
            content=b"# only",
            filename="o.md",
            content_type="text/markdown",
        )
        broken = doc.model_copy(update={"storage_path": "s3://missing"})
        world["registry"].update(broken)
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        final = world["orchestrator"].run(job.parse_job_id)
        assert final.status == ParseJobStatus.FAILED
        # Job-level error_code пропагирует РЕАЛЬНУЮ причину сбоя документа
        # (тут — отсутствующий raw file), а не жёстко зашитый generic-код.
        assert final.error_code == ParseErrorCode.RAW_FILE_NOT_FOUND


class TestEvents:
    def test_create_and_run_emit_events(self) -> None:
        world = _make_world()
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_1",
            content=b"# T",
            filename="a.md",
            content_type="text/markdown",
        )
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        world["orchestrator"].run(job.parse_job_id)
        types = {e.event_type for e in world["bus"].captured}
        assert "parse.job.created" in types
        assert "parse.job.started" in types
        assert "parse.document.started" in types
        assert "parse.document.completed" in types
        assert "parse.sections.created" in types
        assert "parse.job.completed" in types

    def test_low_confidence_event_emitted(self) -> None:
        world = _make_world()
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_1",
            content=b"random text without any classifier keywords",
            filename="x.txt",
            content_type="text/plain",
        )
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        world["orchestrator"].run(job.parse_job_id)
        low_events = [
            e for e in world["bus"].captured if e.event_type == "parse.section.low_confidence"
        ]
        assert len(low_events) >= 1


class TestLifecycleIntegration:
    def test_processing_log_info_on_success(self) -> None:
        world = _make_world()
        _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_1",
            content=b"# Title\n\nbody",
            filename="a.md",
            content_type="text/markdown",
        )
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        world["orchestrator"].run(job.parse_job_id)
        entries = world["log"].list_for_document("src_1")
        parsing_logs = [e for e in entries if e.step.value == "parsing"]
        assert parsing_logs
        assert any(e.level.value == "info" for e in parsing_logs)

    def test_processing_log_error_on_fail(self) -> None:
        world = _make_world()
        doc = _add_source(
            world=world,
            setup_job_id="sj_1",
            source_document_id="src_1",
            content=b"# t",
            filename="a.md",
            content_type="text/markdown",
        )
        world["registry"].update(doc.model_copy(update={"storage_path": "s3://missing"}))
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        world["orchestrator"].run(job.parse_job_id)
        entries = world["log"].list_for_document("src_1")
        assert any(e.level.value == "error" for e in entries)


# ============================================================
# Classification resilience (SETUP-13 / ADR-HTC-09 wiring): один сбойный
# вызов LLM-классификатора не должен ронять весь документ и терять уже
# сделанную работу; несколько сбоев ПОДРЯД — системная проблема, документ
# останавливается, но с честным (не нулевым) отчётом о прогрессе.
# ============================================================


class _FlakyClassifier:
    """apply_to_sections вызывается по одной секции за раз (по одному
    вызову на section в цикле orchestrator'а) — кидает LLMUnavailableError
    на заданных по счётчику вызовах, иначе классифицирует "успешно"."""

    def __init__(self, fail_at_calls: set[int]) -> None:
        self._fail_at_calls = fail_at_calls
        self.call_count = 0

    def apply_to_sections(self, sections):  # noqa: ANN001, ANN201
        self.call_count += 1
        if self.call_count in self._fail_at_calls:
            raise LLMUnavailableError(f"simulated failure at call {self.call_count}")
        [section] = sections
        return [
            section.model_copy(
                update={"confidence": 0.9, "classification_method": "fake_llm"}
            )
        ]


def _five_section_doc(world: dict[str, Any]) -> None:
    _add_source(
        world=world,
        setup_job_id="sj_1",
        source_document_id="src_1",
        content=(
            b"# A\n\nBody A\n\n# B\n\nBody B\n\n# C\n\nBody C\n\n"
            b"# D\n\nBody D\n\n# E\n\nBody E"
        ),
        filename="five.md",
        content_type="text/markdown",
    )


class TestClassificationResilience:
    def test_isolated_failure_is_skipped_not_fatal(self) -> None:
        # Один сбой (call #2 из 5) — секция помечается неклассифицированной,
        # обработка документа продолжается до конца.
        classifier = _FlakyClassifier(fail_at_calls={2})
        world = _make_world(classifier=classifier)
        _five_section_doc(world)
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        final = world["orchestrator"].run(job.parse_job_id)

        assert final.status == ParseJobStatus.COMPLETED
        assert final.total_sections == 5
        sections = world["section_repo"].list_for_document("src_1")
        assert len(sections) == 5
        failed_sections = [
            s for s in sections if s.classification_method == "classifier_tree_failed"
        ]
        assert len(failed_sections) == 1
        assert failed_sections[0].confidence == 0.0
        ok_sections = [s for s in sections if s.classification_method == "fake_llm"]
        assert len(ok_sections) == 4

    def test_consecutive_failures_trip_circuit_breaker(self) -> None:
        # 3 сбоя ПОДРЯД (calls #2,#3,#4 из 5) — считается системной
        # проблемой: документ останавливается как FAILED, но отчёт честно
        # показывает 1 реально обработанную секцию, а не 0.
        classifier = _FlakyClassifier(fail_at_calls={2, 3, 4})
        world = _make_world(classifier=classifier)
        _five_section_doc(world)
        job = world["orchestrator"].create_parse_job(setup_job_id="sj_1", requested_by="user-1")
        final = world["orchestrator"].run(job.parse_job_id)

        assert final.status == ParseJobStatus.FAILED
        assert final.error_code == ParseErrorCode.CLASSIFICATION_FAILED
        # Прогресс до срабатывания circuit breaker не должен теряться из
        # job-level счётчиков (было: total_sections всегда 0 при FAILED).
        # 3 секции обработаны до триггера: call#1 успех + call#2,#3 —
        # изолированные сбои (тоже сохраняются, просто неклассифицированные);
        # call#4 — третий сбой ПОДРЯД, обрывает документ до сохранения.
        assert final.total_sections == 3
        report = world["report_repo"].get_for_document_in_job(job.parse_job_id, "src_1")
        assert report is not None
        assert report.summary.sections_count == 3
        assert report.errors[0]["code"] == ParseErrorCode.CLASSIFICATION_FAILED.value
