"""Integration-тесты wiring SETUP-12 (Wiring-1/2/3).

Покрывают:
- Wiring-1: feature flag ``FE_BOT_TAXONOMY_MODE`` переключает
  classifier factory в dependencies.py.
- Wiring-2: orchestrator-уровень — ConfidenceCalculator принимает
  parser_classification_state, RAGCardGenerationOrchestrator
  обогащает front_matter taxonomy-полями.
- Wiring-3: VectorIndexerService переносит taxonomy fields из
  card.front_matter в Qdrant payload; RetrievalService применяет
  TaxonomyFilter (exact + bitwise post-filter).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from fe_bot.taxonomy import (
    BitTest,
    TaxonomyFilter,
)
from fe_bot.vector_index.client import (
    InMemoryVectorIndexClient,
    VectorPoint,
)
from fe_bot.vector_index.service import _extract_taxonomy_payload

pytestmark = pytest.mark.integration


# ----------------------------------------------------------------------
# Wiring-1: feature-flag classifier factory
# ----------------------------------------------------------------------


class TestWiring1ClassifierFactory:
    def test_default_returns_rule_based(self) -> None:
        os.environ.pop("FE_BOT_TAXONOMY_MODE", None)
        # Imported lazily: re-import module to re-evaluate factory
        from fe_bot.api.dependencies import _build_section_classifier
        from fe_bot.setup.parser.classifier import SectionClassifier

        clf = _build_section_classifier()
        assert isinstance(clf, SectionClassifier)

    def test_llm_mode_returns_classifier_tree_section_classifier(self, monkeypatch) -> None:
        # ADR-HTC-09: SETUP-13 (generic-depth дерево классификаторов)
        # заменяет SETUP-12 (HierarchicalSectionClassifier / bitmap) —
        # FE_BOT_TAXONOMY_MODE=llm теперь строит ClassifierTreeSectionClassifier.
        monkeypatch.setenv("FE_BOT_TAXONOMY_MODE", "llm")
        from fe_bot.api.dependencies import _build_section_classifier
        from fe_bot.classifier.section_classifier_adapter import (
            ClassifierTreeSectionClassifier,
        )

        clf = _build_section_classifier()
        assert isinstance(clf, ClassifierTreeSectionClassifier)

    def test_unknown_mode_falls_back_to_rule_based(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("FE_BOT_TAXONOMY_MODE", "bananas")
        from fe_bot.api.dependencies import _build_section_classifier
        from fe_bot.setup.parser.classifier import SectionClassifier

        clf = _build_section_classifier()
        assert isinstance(clf, SectionClassifier)


# ----------------------------------------------------------------------
# Wiring-1: doc_type_detector factory
# ----------------------------------------------------------------------


class TestWiring2DocTypeDetectorFactory:
    def test_default_returns_legacy(self) -> None:
        os.environ.pop("FE_BOT_TAXONOMY_MODE", None)
        from fe_bot.api.dependencies import _build_doc_type_detector
        from fe_bot.setup.rag_card_generation.doc_type_detector import (
            DocTypeDetector,
        )

        d = _build_doc_type_detector()
        assert isinstance(d, DocTypeDetector)

    def test_llm_mode_returns_taxonomy_aware(self, monkeypatch) -> None:
        monkeypatch.setenv("FE_BOT_TAXONOMY_MODE", "llm")
        from fe_bot.api.dependencies import _build_doc_type_detector
        from fe_bot.taxonomy import TaxonomyDocTypeDetector

        d = _build_doc_type_detector()
        assert isinstance(d, TaxonomyDocTypeDetector)


# ----------------------------------------------------------------------
# Wiring-3: taxonomy payload extraction from front_matter
# ----------------------------------------------------------------------


class TestExtractTaxonomyPayload:
    def test_empty_front_matter(self) -> None:
        assert _extract_taxonomy_payload(None) == {}
        assert _extract_taxonomy_payload({}) == {}

    def test_extracts_known_keys(self) -> None:
        fm = {
            "doc_id": "x",  # not taxonomy → dropped
            "taxonomy_version_id": "v1.0.0",
            "taxonomy_node_id": "task",
            "taxonomy_path": ["task", "pvo"],
            "classification_bitmap": 0b101,
            "primary_l0": "task",
            "primary_l1": "pvo",
            "unknown_at_level": 2,
        }
        out = _extract_taxonomy_payload(fm)
        assert "doc_id" not in out
        assert out["taxonomy_version_id"] == "v1.0.0"
        assert out["taxonomy_path"] == ["task", "pvo"]
        assert out["classification_bitmap"] == 0b101
        assert out["primary_l0"] == "task"
        assert out["unknown_at_level"] == 2


# ----------------------------------------------------------------------
# Wiring-3: VectorPoint.payload содержит taxonomy fields
# ----------------------------------------------------------------------


class TestMakePointWithTaxonomy:
    def test_extra_payload_appended(self) -> None:
        from schemas.rag.chunk import Chunk, ChunkType
        from schemas.rag.embedding import Embedding, EmbeddingStatus

        from fe_bot.vector_index.client import make_point

        chunk = Chunk(
            chunk_id="ch_1",
            doc_id="schema.x.v1",
            chunk_type=ChunkType.SUMMARY,
            chunk_text="body text",
            embedding_text="body text",
            priority=10,
            created_at=datetime.now(tz=UTC),
            token_count=None,
        )
        embedding = Embedding(
            embedding_id="em_1",
            chunk_id="ch_1",
            doc_id="schema.x.v1",
            embedding_vector=[0.1, 0.2, 0.3],
            embedding_model="m",
            dimension=3,
            index_version=None,
            created_at=datetime.now(tz=UTC),
            status=EmbeddingStatus.CREATED,
        )
        point = make_point(
            chunk=chunk,
            embedding=embedding,
            doc_type="schema_card",
            extra_payload={
                "primary_l0": "schema",
                "taxonomy_path": ["schema", "etl"],
                "classification_bitmap": 0b11,
            },
        )
        assert point.payload["primary_l0"] == "schema"
        assert point.payload["taxonomy_path"] == ["schema", "etl"]
        # Базовые поля не перетёрты
        assert point.payload["doc_id"] == "schema.x.v1"
        assert point.payload["doc_type"] == "schema_card"


# ----------------------------------------------------------------------
# Wiring-3: RetrievalService с TaxonomyFilter
# ----------------------------------------------------------------------


class _StubEmbeddingService:
    def embed_chunk(self, chunk):  # noqa: ANN001
        from schemas.rag.embedding import Embedding, EmbeddingStatus

        return Embedding(
            embedding_id="qe",
            chunk_id="__query__",
            doc_id="__query__",
            embedding_vector=[1.0, 0.0, 0.0],
            embedding_model="m",
            dimension=3,
            index_version=None,
            created_at=datetime.now(tz=UTC),
            status=EmbeddingStatus.CREATED,
        )


def _index_with_two_docs() -> InMemoryVectorIndexClient:
    """Один schema_card payload + один task_card payload, оба
    с taxonomy полями."""
    client = InMemoryVectorIndexClient()
    p1 = VectorPoint(
        chunk_id="c1",
        doc_id="schema.x.v1",
        doc_type="schema_card",
        chunk_type="body",
        vector=[1.0, 0.0, 0.0],
        payload={
            "doc_id": "schema.x.v1",
            "primary_l0": "schema",
            "taxonomy_path": ["schema", "etl"],
            "classification_bitmap": 0b0000000000_0000000001_0000000010,  # schema bit + L1 bit 0
            "taxonomy_version": "v1.0.0",
        },
    )
    p2 = VectorPoint(
        chunk_id="c2",
        doc_id="task.x.v1",
        doc_type="task_card",
        chunk_type="body",
        vector=[1.0, 0.0, 0.0],
        payload={
            "doc_id": "task.x.v1",
            "primary_l0": "task",
            "taxonomy_path": ["task", "pvo"],
            "classification_bitmap": 0b0000000000_0000000001_0000000001,  # task + pvo L1 bit 0
            "taxonomy_version": "v1.0.0",
        },
    )
    client.upsert(collection="rag_schema_card", point=p1)
    client.upsert(collection="rag_task_card", point=p2)
    return client


class TestRetrievalServiceTaxonomyFilter:
    def test_exact_filter_routes_through_vector_search(self) -> None:
        from fe_bot.retrieval.service import (
            RetrievalRequest,
            RetrievalService,
        )

        client = _index_with_two_docs()
        svc = RetrievalService(
            embedding=_StubEmbeddingService(),
            index_client=client,
        )
        req = RetrievalRequest(
            query="anything",
            top_k=10,
            taxonomy_filter=TaxonomyFilter(primary_l0=["schema"]),
        )
        result = svc.search(req)
        # Только schema-карточка должна вернуться
        assert len(result.hits) == 1
        assert result.hits[0].doc_id == "schema.x.v1"

    def test_post_filter_path_prefix(self) -> None:
        from fe_bot.retrieval.service import (
            RetrievalRequest,
            RetrievalService,
        )

        client = _index_with_two_docs()
        svc = RetrievalService(
            embedding=_StubEmbeddingService(),
            index_client=client,
        )
        req = RetrievalRequest(
            query="anything",
            top_k=10,
            taxonomy_filter=TaxonomyFilter(path_prefix=["schema"]),
        )
        result = svc.search(req)
        assert len(result.hits) == 1
        assert result.hits[0].doc_id == "schema.x.v1"

    def test_post_filter_bit_test(self) -> None:
        from fe_bot.retrieval.service import (
            RetrievalRequest,
            RetrievalService,
        )

        client = _index_with_two_docs()
        svc = RetrievalService(
            embedding=_StubEmbeddingService(),
            index_client=client,
        )
        # Bit-test: ищем те, у кого L0 bit 0 (task) установлен.
        req = RetrievalRequest(
            query="anything",
            top_k=10,
            taxonomy_filter=TaxonomyFilter(
                any_bit=[BitTest(level=0, bit_in_level=0)]
            ),
        )
        result = svc.search(req)
        assert len(result.hits) == 1
        assert result.hits[0].doc_id == "task.x.v1"

    def test_no_filter_returns_all(self) -> None:
        from fe_bot.retrieval.service import (
            RetrievalRequest,
            RetrievalService,
        )

        client = _index_with_two_docs()
        svc = RetrievalService(
            embedding=_StubEmbeddingService(),
            index_client=client,
        )
        req = RetrievalRequest(query="anything", top_k=10)
        result = svc.search(req)
        assert len(result.hits) == 2


# ----------------------------------------------------------------------
# Wiring-2: ConfidenceCalculator parser_classification_state propagation
# ----------------------------------------------------------------------


class TestConfidenceCalculatorIntegration:
    def test_parser_state_optional(self) -> None:
        """Backward-compat: ConfidenceCalculator работает без
        parser_classification_state — orchestrator может его не
        передавать в rule_based mode."""
        from schemas.setup.rag_card_generation_report import (
            CardValidationReportDTO,
        )

        from fe_bot.setup.rag_card_generation.confidence_calculator import (
            ConfidenceCalculator,
        )
        from fe_bot.setup.rag_card_generation.llm_adapter import (
            LLMGenerationResult,
        )
        from fe_bot.setup.rag_card_generation.precheck import RAGCardDraft

        precheck = CardValidationReportDTO(
            validation_report_id="val_x",
            doc_id="doc_x",
            card_version="1.0",
            passed=True,
            errors=[],
            warnings=[],
            checked_at=datetime.now(tz=UTC),
        )
        llm = LLMGenerationResult(
            draft=RAGCardDraft(
                doc_id="x.v1",
                doc_type="schema_card",
                title="X",
                body_markdown="body" * 10,
                front_matter={"doc_id": "x.v1", "doc_type": "schema_card"},
                source_files=["x.md"],
                source_sections=["sec_1"],
                retrieval_tags=["x"],
            ),
            attempts=1,
            duration_ms=10,
            model="llama3.2",
            used_fallback=False,
        )
        calc = ConfidenceCalculator()
        d = calc.calculate(
            precheck=precheck, llm_result=llm, ontology_warnings=[]
        )
        assert d.score == 1.0
