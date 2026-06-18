"""SourceDocumentUserMetadata DTO (SETUP-03 / T-S03-005).

Пользовательская metadata источника: tags, description, owner_note, custom labels.
Отделена от system metadata (checksum, storage_path, uploaded_at) — её можно
менять через PATCH /sources/{id}/metadata.

Sanitization: все строковые поля экранируются от HTML/script injection
до сохранения. Этот шаг здесь, в схеме, чтобы любой consumer (REST, internal
service, CLI) получал безопасные значения.

Source of truth — SETUP-03 spec §15.1 (UpdateSourceMetadataRequest), §11.2.
"""

from __future__ import annotations

import html

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_TAGS_COUNT = 20
MAX_TAG_LENGTH = 50
MAX_DESCRIPTION_LENGTH = 2000
MAX_OWNER_NOTE_LENGTH = 500
MAX_CUSTOM_LABELS_COUNT = 10
MAX_CUSTOM_LABEL_KEY_LENGTH = 50
MAX_CUSTOM_LABEL_VALUE_LENGTH = 200


def _sanitize_string(s: str) -> str:
    """Удаляет управляющие символы + экранирует HTML.

    Защита от XSS при render'е в UI. Bidi controls (RLO/LRO) тоже снимаем.
    """
    cleaned = "".join(ch for ch in s if ord(ch) >= 0x20 and ord(ch) != 0x7F)
    return html.escape(cleaned, quote=True)


def _sanitize_optional(s: str | None) -> str | None:
    return _sanitize_string(s) if s is not None else None


class SourceDocumentUserMetadata(BaseModel):
    """Пользовательская metadata source document.

    Хранится в SourceDocument.metadata['user']. Изменяется через PATCH
    /sources/{id}/metadata.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    tags: list[str] = Field(default_factory=list)
    description: str | None = None
    owner_note: str | None = None
    custom_labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_TAGS_COUNT:
            raise ValueError(f"Too many tags: {len(v)} > {MAX_TAGS_COUNT}")
        sanitized: list[str] = []
        for tag in v:
            if not tag or not tag.strip():
                raise ValueError("Tag cannot be empty")
            if len(tag) > MAX_TAG_LENGTH:
                raise ValueError(f"Tag too long: {len(tag)} > {MAX_TAG_LENGTH}")
            sanitized.append(_sanitize_string(tag.strip()))
        return sanitized

    @field_validator("description")
    @classmethod
    def _validate_description(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Description too long: {len(v)} > {MAX_DESCRIPTION_LENGTH}")
        return _sanitize_string(v)

    @field_validator("owner_note")
    @classmethod
    def _validate_owner_note(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) > MAX_OWNER_NOTE_LENGTH:
            raise ValueError(f"owner_note too long: {len(v)} > {MAX_OWNER_NOTE_LENGTH}")
        return _sanitize_string(v)

    @field_validator("custom_labels")
    @classmethod
    def _validate_custom_labels(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > MAX_CUSTOM_LABELS_COUNT:
            raise ValueError(f"Too many custom_labels: {len(v)} > {MAX_CUSTOM_LABELS_COUNT}")
        sanitized: dict[str, str] = {}
        for key, value in v.items():
            if not key or len(key) > MAX_CUSTOM_LABEL_KEY_LENGTH:
                raise ValueError(f"Invalid custom_label key length: {len(key)}")
            if len(value) > MAX_CUSTOM_LABEL_VALUE_LENGTH:
                raise ValueError(f"custom_label value too long: {len(value)}")
            sanitized[_sanitize_string(key)] = _sanitize_string(value)
        return sanitized


class UpdateSourceMetadataRequest(BaseModel):
    """Тело PATCH /sources/{id}/metadata.

    Все поля optional — патчим только то что передано. None значит "не менять".
    Передача `tags=[]` сбрасывает теги; пропуск поля — оставляет как было.
    """

    model_config = ConfigDict(extra="forbid")

    tags: list[str] | None = None
    description: str | None = None
    owner_note: str | None = None
    custom_labels: dict[str, str] | None = None


# Поля, которые НЕЛЬЗЯ менять через PATCH /metadata (§11.2 + AC-26).
# Защита на API-уровне (если кто-то попытается через kwargs/extra).
PROTECTED_FIELDS = frozenset(
    {
        "source_document_id",
        "setup_job_id",
        "filename",
        "content_type",
        "size_bytes",
        "checksum",
        "storage_path",
        "status",
        "uploaded_by",
        "uploaded_at",
        "parsed_at",
        "system_metadata",
    }
)


class SystemMetadataReadOnlyError(ValueError):
    """Попытка изменить protected field через PATCH /metadata."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Field {field_name!r} is system-managed and cannot be patched")


def reject_protected_fields(patch: dict[str, object]) -> None:
    """Raise если patch содержит protected fields."""
    for key in patch:
        if key in PROTECTED_FIELDS:
            raise SystemMetadataReadOnlyError(key)
