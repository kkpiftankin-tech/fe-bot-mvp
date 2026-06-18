"""Unit-тесты ParsedSectionRepository (T-S04-008)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.setup.parser.section_repository import (
    DuplicateSectionError,
    InMemoryParsedSectionRepository,
    ParsedSectionNotFoundError,
)

pytestmark = pytest.mark.unit


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _section(
    *,
    section_id: str = "sec_001",
    source_document_id: str = "src_001",
    parse_job_id: str = "pj_001",
    text: str = "content",
) -> ParsedSection:
    return ParsedSection(
        section_id=section_id,
        parse_job_id=parse_job_id,
        source_document_id=source_document_id,
        parent_section_id=None,
        classification_method="rule_based",
        title="Test",
        section_type=SectionType.OTHER,
        raw_text=text,
        normalized_text=text,
        content_hash=_hash(text),
        confidence=0.8,
        created_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
    )


class TestSave:
    def test_save_and_get(self) -> None:
        repo = InMemoryParsedSectionRepository()
        repo.save(_section())
        assert repo.get("sec_001").section_id == "sec_001"

    def test_get_unknown_raises(self) -> None:
        repo = InMemoryParsedSectionRepository()
        with pytest.raises(ParsedSectionNotFoundError):
            repo.get("nope")

    def test_save_duplicate_raises(self) -> None:
        repo = InMemoryParsedSectionRepository()
        repo.save(_section())
        with pytest.raises(DuplicateSectionError):
            repo.save(_section())


class TestSaveBatchAtomic:
    def test_save_batch_inserts_all(self) -> None:
        repo = InMemoryParsedSectionRepository()
        batch = [
            _section(section_id="s1", text="a"),
            _section(section_id="s2", text="b"),
            _section(section_id="s3", text="c"),
        ]
        repo.save_batch(batch)
        assert len(repo.list_for_document("src_001")) == 3

    def test_save_batch_atomic_rollback_on_conflict(self) -> None:
        """Если хотя бы одна section_id конфликтует — НИ ОДНА не сохраняется."""
        repo = InMemoryParsedSectionRepository()
        repo.save(_section(section_id="existing", text="x"))
        batch = [
            _section(section_id="new_1", text="a"),
            _section(section_id="existing", text="conflict"),  # conflict!
            _section(section_id="new_2", text="b"),
        ]
        with pytest.raises(DuplicateSectionError):
            repo.save_batch(batch)
        # new_1 и new_2 НЕ должны быть в репо.
        assert len(repo.list_for_document("src_001")) == 1
        assert {s.section_id for s in repo.list_for_document("src_001")} == {"existing"}

    def test_save_batch_atomic_rollback_on_internal_duplicate(self) -> None:
        """Если в самом batch'е есть дубликат — rollback всего."""
        repo = InMemoryParsedSectionRepository()
        batch = [
            _section(section_id="s1", text="a"),
            _section(section_id="s1", text="duplicate"),
        ]
        with pytest.raises(DuplicateSectionError):
            repo.save_batch(batch)
        assert repo.list_for_document("src_001") == []


class TestListing:
    def test_list_for_document(self) -> None:
        repo = InMemoryParsedSectionRepository()
        repo.save(_section(section_id="s1", source_document_id="src_A"))
        repo.save(_section(section_id="s2", source_document_id="src_A", text="b"))
        repo.save(_section(section_id="s3", source_document_id="src_B", text="c"))
        items = repo.list_for_document("src_A")
        assert {s.section_id for s in items} == {"s1", "s2"}

    def test_list_for_job(self) -> None:
        repo = InMemoryParsedSectionRepository()
        repo.save(_section(section_id="s1", parse_job_id="pj_A"))
        repo.save(_section(section_id="s2", parse_job_id="pj_A", text="b"))
        repo.save(_section(section_id="s3", parse_job_id="pj_B", text="c"))
        items = repo.list_for_job("pj_A")
        assert {s.section_id for s in items} == {"s1", "s2"}


class TestFindByContentHash:
    def test_find_existing(self) -> None:
        repo = InMemoryParsedSectionRepository()
        section = _section(text="duplicate-candidate")
        repo.save(section)
        found = repo.find_by_content_hash(section.content_hash)
        assert found is not None
        assert found.section_id == section.section_id

    def test_find_none_for_unknown_hash(self) -> None:
        repo = InMemoryParsedSectionRepository()
        assert repo.find_by_content_hash("z" * 64) is None
