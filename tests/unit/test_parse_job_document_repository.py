"""Unit-тесты ParseJobDocumentRepository (T-S04-007)."""

from __future__ import annotations

import pytest
from schemas.setup.parse_job_document import (
    ParseJobDocument,
    ParseJobDocumentStatus,
)

from fe_bot.setup.parser.document_repository import (
    InMemoryParseJobDocumentRepository,
    ParseJobDocumentNotFoundError,
)

pytestmark = pytest.mark.unit


def _doc(
    *,
    pjd_id: str = "pjd_001",
    parse_job_id: str = "pj_001",
    source_document_id: str = "src_001",
    status: ParseJobDocumentStatus = ParseJobDocumentStatus.PENDING,
) -> ParseJobDocument:
    return ParseJobDocument(
        parse_job_document_id=pjd_id,
        parse_job_id=parse_job_id,
        source_document_id=source_document_id,
        status=status,
    )


class TestBasics:
    def test_add_and_get(self) -> None:
        repo = InMemoryParseJobDocumentRepository()
        repo.add(_doc())
        assert repo.get("pjd_001").source_document_id == "src_001"

    def test_get_unknown_raises(self) -> None:
        repo = InMemoryParseJobDocumentRepository()
        with pytest.raises(ParseJobDocumentNotFoundError):
            repo.get("nope")

    def test_update_changes_status(self) -> None:
        repo = InMemoryParseJobDocumentRepository()
        repo.add(_doc())
        repo.update(_doc(status=ParseJobDocumentStatus.PROCESSING))
        assert repo.get("pjd_001").status == ParseJobDocumentStatus.PROCESSING


class TestListing:
    def test_list_for_job_preserves_order(self) -> None:
        repo = InMemoryParseJobDocumentRepository()
        repo.add(_doc(pjd_id="pjd_A"))
        repo.add(_doc(pjd_id="pjd_B", source_document_id="src_2"))
        repo.add(_doc(pjd_id="pjd_C", source_document_id="src_3"))
        items = repo.list_for_job("pj_001")
        assert [i.parse_job_document_id for i in items] == [
            "pjd_A",
            "pjd_B",
            "pjd_C",
        ]

    def test_list_pending_excludes_completed(self) -> None:
        repo = InMemoryParseJobDocumentRepository()
        repo.add(_doc(pjd_id="pjd_1", status=ParseJobDocumentStatus.PENDING))
        repo.add(_doc(pjd_id="pjd_2", status=ParseJobDocumentStatus.COMPLETED))
        repo.add(_doc(pjd_id="pjd_3", status=ParseJobDocumentStatus.PENDING))
        pending = repo.list_pending_for_job("pj_001")
        assert [p.parse_job_document_id for p in pending] == ["pjd_1", "pjd_3"]
