"""Unit-тесты RAGCardGenerationJobSectionRepository (SETUP-05 / T-S05-009)."""

from __future__ import annotations

import pytest
from schemas.setup.rag_card_generation_job_section import (
    RAGCardGenerationJobSection,
    RAGCardGenerationJobSectionStatus,
)

from fe_bot.setup.rag_card_generation.job_section_repository import (
    DuplicateGenerationJobSectionError,
    GenerationJobSectionNotFoundError,
    InMemoryRAGCardGenerationJobSectionRepository,
)

pytestmark = pytest.mark.unit


def _section(
    *,
    section_id: str = "sec_001",
    generation_job_section_id: str = "gjs_001",
    generation_job_id: str = "gen_001",
    status: RAGCardGenerationJobSectionStatus = RAGCardGenerationJobSectionStatus.PENDING,
    generated_doc_id: str | None = None,
) -> RAGCardGenerationJobSection:
    return RAGCardGenerationJobSection(
        generation_job_section_id=generation_job_section_id,
        generation_job_id=generation_job_id,
        section_id=section_id,
        source_document_id="src_001",
        status=status,
        generated_doc_id=generated_doc_id,
    )


class TestCRUD:
    def test_add_and_get(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        repo.add(_section())
        loaded = repo.get("gjs_001")
        assert loaded.section_id == "sec_001"

    def test_duplicate_add_raises(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        repo.add(_section())
        with pytest.raises(DuplicateGenerationJobSectionError):
            repo.add(_section())

    def test_unknown_get_raises(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        with pytest.raises(GenerationJobSectionNotFoundError):
            repo.get("ghost")

    def test_update(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        repo.add(_section())
        sec = repo.get("gjs_001")
        sec.status = RAGCardGenerationJobSectionStatus.PROCESSING
        repo.update(sec)
        assert repo.get("gjs_001").status == RAGCardGenerationJobSectionStatus.PROCESSING


class TestListing:
    def test_list_preserves_insertion_order(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        for i in range(3):
            repo.add(
                _section(
                    section_id=f"sec_{i:03d}",
                    generation_job_section_id=f"gjs_{i:03d}",
                )
            )
        listing = repo.list_for_job("gen_001")
        assert [s.section_id for s in listing] == ["sec_000", "sec_001", "sec_002"]

    def test_list_pending_only(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        repo.add(_section(generation_job_section_id="gjs_a"))
        repo.add(
            _section(
                generation_job_section_id="gjs_b",
                status=RAGCardGenerationJobSectionStatus.COMPLETED,
            )
        )
        pending = repo.list_pending_for_job("gen_001")
        assert len(pending) == 1
        assert pending[0].generation_job_section_id == "gjs_a"


class TestDocIdLookup:
    def test_find_existing_doc_id(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        repo.add(_section(generated_doc_id="analytics.x.v1"))
        found = repo.find_existing_doc_id("analytics.x.v1")
        assert found is not None
        assert found.generated_doc_id == "analytics.x.v1"

    def test_find_existing_doc_id_missing(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        repo.add(_section(generated_doc_id="other.v1"))
        assert repo.find_existing_doc_id("missing.v1") is None


class TestSnapshot:
    def test_roundtrip(self) -> None:
        repo = InMemoryRAGCardGenerationJobSectionRepository()
        repo.add(_section(generation_job_section_id="a"))
        repo.add(_section(generation_job_section_id="b"))
        snap = repo.snapshot()
        repo2 = InMemoryRAGCardGenerationJobSectionRepository()
        repo2.restore(snap)
        assert {s.generation_job_section_id for s in repo2.list_for_job("gen_001")} == {
            "a",
            "b",
        }
