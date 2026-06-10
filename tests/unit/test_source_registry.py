"""Тесты Source Registry Service (T-S01-014)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus

from fe_bot.setup.source_registry.service import (
    DuplicateDocumentError,
    InMemorySourceRegistry,
    SourceDocumentNotFoundError,
)

pytestmark = pytest.mark.unit


def _make_doc(
    source_document_id: str = "src_1",
    setup_job_id: str = "setup_1",
    checksum: str = "a" * 64,
    filename: str = "doc.md",
) -> SourceDocument:
    return SourceDocument(
        source_document_id=source_document_id,
        setup_job_id=setup_job_id,
        filename=filename,
        content_type="text/markdown",
        storage_path=f"s3://source-documents/{setup_job_id}/{source_document_id}/{filename}",
        size_bytes=1024,
        checksum=checksum,
        uploaded_by="u1",
        uploaded_at=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def registry() -> InMemorySourceRegistry:
    return InMemorySourceRegistry()


class TestAddGet:
    def test_add_and_get(self, registry: InMemorySourceRegistry) -> None:
        doc = _make_doc()
        registry.add(doc)
        fetched = registry.get(doc.source_document_id)
        assert fetched.source_document_id == doc.source_document_id
        assert fetched.checksum == doc.checksum

    def test_get_unknown_raises(self, registry: InMemorySourceRegistry) -> None:
        with pytest.raises(SourceDocumentNotFoundError):
            registry.get("nonexistent")

    def test_get_returns_independent_copy(
        self, registry: InMemorySourceRegistry
    ) -> None:
        doc = _make_doc()
        registry.add(doc)
        fetched = registry.get(doc.source_document_id)
        fetched.status = SourceDocumentStatus.PARSED
        # Изменение не должно отразиться в хранилище
        again = registry.get(doc.source_document_id)
        assert again.status == SourceDocumentStatus.UPLOADED


class TestDedup:
    def test_duplicate_checksum_within_job_raises(
        self, registry: InMemorySourceRegistry
    ) -> None:
        doc1 = _make_doc(source_document_id="src_1", checksum="b" * 64)
        doc2 = _make_doc(source_document_id="src_2", checksum="b" * 64)
        registry.add(doc1)
        with pytest.raises(DuplicateDocumentError) as exc:
            registry.add(doc2)
        assert exc.value.existing_source_document_id == "src_1"
        assert exc.value.checksum == "b" * 64

    def test_same_checksum_different_jobs_allowed(
        self, registry: InMemorySourceRegistry
    ) -> None:
        # Один и тот же документ может быть загружен в разные setup_job_id.
        doc1 = _make_doc(setup_job_id="job_a", source_document_id="src_1")
        doc2 = _make_doc(setup_job_id="job_b", source_document_id="src_2")
        registry.add(doc1)
        registry.add(doc2)
        assert registry.get("src_1").setup_job_id == "job_a"
        assert registry.get("src_2").setup_job_id == "job_b"

    def test_find_by_checksum(self, registry: InMemorySourceRegistry) -> None:
        doc = _make_doc(checksum="c" * 64)
        registry.add(doc)
        found = registry.find_by_checksum("setup_1", "c" * 64)
        assert found is not None
        assert found.source_document_id == doc.source_document_id

    def test_find_by_checksum_miss(self, registry: InMemorySourceRegistry) -> None:
        assert registry.find_by_checksum("setup_1", "d" * 64) is None


class TestListing:
    def test_list_for_job_empty(self, registry: InMemorySourceRegistry) -> None:
        assert registry.list_for_job("nonexistent") == []

    def test_list_for_job_preserves_order(
        self, registry: InMemorySourceRegistry
    ) -> None:
        for i in range(3):
            registry.add(
                _make_doc(
                    source_document_id=f"src_{i}",
                    checksum=str(i) * 64,
                    filename=f"doc_{i}.md",
                )
            )
        docs = registry.list_for_job("setup_1")
        assert [d.source_document_id for d in docs] == ["src_0", "src_1", "src_2"]

    def test_list_for_job_filters_by_setup_id(
        self, registry: InMemorySourceRegistry
    ) -> None:
        registry.add(_make_doc(setup_job_id="job_a", checksum="a" * 64))
        registry.add(
            _make_doc(setup_job_id="job_b", source_document_id="src_2", checksum="b" * 64)
        )
        assert len(registry.list_for_job("job_a")) == 1
        assert len(registry.list_for_job("job_b")) == 1


class TestUpdate:
    def test_update_status(self, registry: InMemorySourceRegistry) -> None:
        doc = _make_doc()
        registry.add(doc)
        doc.status = SourceDocumentStatus.PARSED
        doc.parsed_at = datetime(2026, 6, 4, 11, 0, tzinfo=UTC)
        registry.update(doc)
        updated = registry.get(doc.source_document_id)
        assert updated.status == SourceDocumentStatus.PARSED
        assert updated.parsed_at is not None

    def test_update_unknown_raises(self, registry: InMemorySourceRegistry) -> None:
        with pytest.raises(SourceDocumentNotFoundError):
            registry.update(_make_doc(source_document_id="nope"))

    def test_update_cannot_change_checksum(
        self, registry: InMemorySourceRegistry
    ) -> None:
        doc = _make_doc(checksum="a" * 64)
        registry.add(doc)
        doc.checksum = "b" * 64
        with pytest.raises(ValueError, match="checksum"):
            registry.update(doc)
