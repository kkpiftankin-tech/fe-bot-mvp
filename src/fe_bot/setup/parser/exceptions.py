"""Ошибки парсеров."""

from __future__ import annotations


class ParserError(Exception):
    """Базовая ошибка парсера."""

    def __init__(self, message: str, *, filename: str | None = None) -> None:
        self.filename = filename
        super().__init__(message)


class UnsupportedFormatError(ParserError):
    """Формат документа не поддерживается этим парсером (см. PARSER_FAILED §18.2)."""


class ParseFailedError(ParserError):
    """Парсинг технически неудачен (поврежден файл, неожиданный формат)."""
