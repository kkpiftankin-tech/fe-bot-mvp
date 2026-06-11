"""Unit-тесты UserMetadata DTO + sanitization (T-S03-005)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from schemas.setup.source_document_metadata import (
    MAX_CUSTOM_LABELS_COUNT,
    MAX_DESCRIPTION_LENGTH,
    MAX_OWNER_NOTE_LENGTH,
    MAX_TAG_LENGTH,
    MAX_TAGS_COUNT,
    PROTECTED_FIELDS,
    SourceDocumentUserMetadata,
    SystemMetadataReadOnlyError,
    UpdateSourceMetadataRequest,
    reject_protected_fields,
)

pytestmark = pytest.mark.unit


class TestUserMetadataValidation:
    def test_valid_minimal(self) -> None:
        m = SourceDocumentUserMetadata()
        assert m.tags == []
        assert m.description is None

    def test_valid_with_fields(self) -> None:
        m = SourceDocumentUserMetadata(
            tags=["naval", "schema"],
            description="Описание ТТХ",
            owner_note="Проверено экспертом",
            custom_labels={"priority": "high", "team": "rag"},
        )
        assert m.tags == ["naval", "schema"]
        assert m.description == "Описание ТТХ"

    def test_too_many_tags_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocumentUserMetadata(
                tags=["tag" + str(i) for i in range(MAX_TAGS_COUNT + 1)]
            )

    def test_tag_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocumentUserMetadata(tags=["x" * (MAX_TAG_LENGTH + 1)])

    def test_empty_tag_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocumentUserMetadata(tags=[""])

    def test_description_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocumentUserMetadata(description="x" * (MAX_DESCRIPTION_LENGTH + 1))

    def test_owner_note_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocumentUserMetadata(owner_note="x" * (MAX_OWNER_NOTE_LENGTH + 1))

    def test_too_many_custom_labels(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocumentUserMetadata(
                custom_labels={f"k{i}": "v" for i in range(MAX_CUSTOM_LABELS_COUNT + 1)}
            )

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocumentUserMetadata(
                tags=[],
                hacker_field="evil",  # type: ignore[call-arg]
            )


class TestSanitization:
    """Защита от XSS / HTML injection."""

    def test_description_html_escaped(self) -> None:
        m = SourceDocumentUserMetadata(description="<script>alert(1)</script>")
        assert "<script>" not in m.description  # type: ignore[operator]
        assert "&lt;script&gt;" in m.description  # type: ignore[operator]

    def test_tag_html_escaped(self) -> None:
        m = SourceDocumentUserMetadata(tags=["<b>bold</b>"])
        assert "<b>" not in m.tags[0]
        assert "&lt;b&gt;" in m.tags[0]

    def test_owner_note_html_escaped(self) -> None:
        m = SourceDocumentUserMetadata(owner_note='"><img src=x onerror=alert(1)>')
        assert "<img" not in m.owner_note  # type: ignore[operator]
        assert "&quot;" in m.owner_note  # type: ignore[operator]

    def test_custom_label_html_escaped(self) -> None:
        m = SourceDocumentUserMetadata(
            custom_labels={"key": "<svg onload=alert(1)>"}
        )
        assert "<svg" not in m.custom_labels["key"]

    def test_control_chars_stripped_from_description(self) -> None:
        m = SourceDocumentUserMetadata(description="bad\x00\x01 text\x7f")
        assert "\x00" not in (m.description or "")
        assert "\x01" not in (m.description or "")
        assert "\x7f" not in (m.description or "")

    def test_tag_trimmed(self) -> None:
        m = SourceDocumentUserMetadata(tags=["  spaces  "])
        assert m.tags[0] == "spaces"


class TestProtectedFields:
    """AC-26: protected fields нельзя менять через PATCH."""

    def test_protected_fields_includes_system_fields(self) -> None:
        for field in (
            "source_document_id",
            "setup_job_id",
            "checksum",
            "storage_path",
            "status",
            "uploaded_by",
            "uploaded_at",
        ):
            assert field in PROTECTED_FIELDS

    def test_reject_protected_field_raises(self) -> None:
        with pytest.raises(SystemMetadataReadOnlyError) as exc:
            reject_protected_fields({"checksum": "evil"})
        assert exc.value.field_name == "checksum"

    def test_reject_passes_for_user_fields(self) -> None:
        reject_protected_fields(
            {"tags": ["a"], "description": "ok", "owner_note": "ok"}
        )  # no raise

    def test_reject_passes_for_empty_patch(self) -> None:
        reject_protected_fields({})  # no raise


class TestUpdateSourceMetadataRequest:
    def test_partial_update_allowed(self) -> None:
        """Только tags — description остаётся как было (None)."""
        req = UpdateSourceMetadataRequest(tags=["new"])
        assert req.tags == ["new"]
        assert req.description is None

    def test_empty_request_is_noop(self) -> None:
        req = UpdateSourceMetadataRequest()
        assert req.tags is None
        assert req.description is None

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            UpdateSourceMetadataRequest(
                tags=[], hacker_field="evil"  # type: ignore[call-arg]
            )
