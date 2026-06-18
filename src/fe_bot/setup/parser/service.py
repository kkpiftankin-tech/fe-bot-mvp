"""Document Parser Service (SVC-07).

Диспатчер по content_type. Делегирует к format-specific парсерам.
Обновляет SourceDocument.status: uploaded → parsed | failed.

Source: SETUP-01 §11.2,
docs/03-architecture/services/setup-services.md#svc-07-document-parser-service.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from schemas.setup.parsed_section import ParsedSection
from schemas.setup.source_document import SourceDocument, SourceDocumentStatus

from fe_bot.setup.parser.exceptions import (
    ParseFailedError,
    ParserError,
    UnsupportedFormatError,
)
from fe_bot.setup.parser.markdown_parser import parse_markdown
from fe_bot.setup.parser.text_parsers import (
    parse_csv,
    parse_docx,
    parse_json,
    parse_pdf,
    parse_plain_text,
    parse_xlsx,
)
from fe_bot.setup.source_registry.service import SourceRegistry
from fe_bot.storage.artifact_service import ArtifactStorage


class DocumentParserService:
    """Парсит исходные документы в ParsedSection и обновляет статус."""

    def __init__(
        self,
        *,
        artifact_storage: ArtifactStorage,
        source_registry: SourceRegistry,
    ) -> None:
        self._storage = artifact_storage
        self._registry = source_registry

    def parse(self, document: SourceDocument) -> list[ParsedSection]:
        """Загружает файл из storage, парсит, обновляет SourceDocument.

        Raises:
            UnsupportedFormatError: формат не поддержан.
            ParseFailedError: технический сбой парсинга.
        """
        try:
            stored = self._storage.download(document.storage_path)
        except Exception as exc:
            self._mark_failed(document, f"Storage download failed: {exc}")
            raise ParseFailedError(
                f"Cannot download document: {exc}", filename=document.filename
            ) from exc

        try:
            sections = self._dispatch(document, stored.data)
        except ParserError as exc:
            self._mark_failed(document, str(exc))
            raise

        # Успех — помечаем parsed.
        updated = document.model_copy(
            update={
                "status": SourceDocumentStatus.PARSED,
                "parsed_at": datetime.now(tz=UTC),
                "error_message": None,
            }
        )
        self._registry.update(updated)
        return sections

    def _dispatch(self, document: SourceDocument, data: bytes) -> list[ParsedSection]:
        kwargs = {
            "source_document_id": document.source_document_id,
            "setup_job_id": document.setup_job_id,
            "filename": document.filename,
        }
        if document.content_type == "text/markdown":
            return parse_markdown(text=data.decode("utf-8-sig"), **kwargs)
        if document.content_type == "text/plain":
            return parse_plain_text(text=data.decode("utf-8-sig"), **kwargs)
        if document.content_type == "text/csv":
            return parse_csv(data=data, **kwargs)
        if document.content_type == "application/json":
            return parse_json(data=data, **kwargs)
        if document.content_type == "application/pdf":
            return parse_pdf(**kwargs)
        if (
            document.content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return parse_docx(**kwargs)
        if (
            document.content_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ):
            return parse_xlsx(**kwargs)
        raise UnsupportedFormatError(
            f"No parser registered for content_type={document.content_type!r}",
            filename=document.filename,
        )

    def _mark_failed(self, document: SourceDocument, message: str) -> None:
        # Не давать ошибке регистрации перекрыть исходную ошибку парсинга.
        with contextlib.suppress(Exception):
            self._registry.update(
                document.model_copy(
                    update={
                        "status": SourceDocumentStatus.FAILED,
                        "error_message": message[:4000],
                    }
                )
            )
