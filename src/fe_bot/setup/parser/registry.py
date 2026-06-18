"""ParserRegistry + ParserStrategy Protocol (SETUP-04 / T-S04-010).

Реестр стратегий парсинга по content_type. Используется
DocumentParserOrchestrator для диспатча.
"""

from __future__ import annotations

from typing import Protocol

from schemas.setup.parse_job import ParserStrategy as ParserStrategyEnum
from schemas.setup.parsed_section import ParsedSection


class UnsupportedFormatError(ValueError):
    """Content-type не поддерживается ни одной стратегией."""

    def __init__(self, content_type: str) -> None:
        self.content_type = content_type
        super().__init__(f"Unsupported parse format: {content_type!r}")


class ParseFailedError(RuntimeError):
    """Стратегия не смогла извлечь содержимое.

    error_code позволяет downstream'у различать причины (PDF_TEXT_LAYER_NOT_FOUND,
    DOCX_EXTRACTION_FAILED, JSON_PARSE_FAILED, etc.).
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        filename: str | None = None,
    ) -> None:
        self.error_code = error_code
        self.filename = filename
        super().__init__(message)


class ParserStrategy(Protocol):
    """Контракт парсера одного формата.

    Принимает raw bytes файла + id'шники, возвращает список секций.
    Должен бросать `ParseFailedError` при неудаче извлечения.
    """

    def parse(
        self,
        *,
        data: bytes,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
    ) -> list[ParsedSection]: ...


# Маппинг content_type → ParserStrategy enum (§4.1, §16 спека).
_CONTENT_TYPE_MAPPING: dict[str, ParserStrategyEnum] = {
    "text/markdown": ParserStrategyEnum.MARKDOWN,
    "text/plain": ParserStrategyEnum.TEXT,
    "text/csv": ParserStrategyEnum.CSV,
    "application/json": ParserStrategyEnum.JSON,
    "application/pdf": ParserStrategyEnum.PDF_TEXT,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        ParserStrategyEnum.DOCX
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (ParserStrategyEnum.XLSX),
}


class ParserRegistry:
    """Реестр зарегистрированных стратегий."""

    def __init__(self) -> None:
        self._strategies: dict[ParserStrategyEnum, ParserStrategy] = {}

    def register(self, strategy_id: ParserStrategyEnum, strategy: ParserStrategy) -> None:
        """Регистрирует стратегию. Повторная регистрация — override."""
        self._strategies[strategy_id] = strategy

    def get_strategy(self, content_type: str) -> ParserStrategy:
        """Возвращает стратегию по content_type.

        Raises:
            UnsupportedFormatError: content_type не в маппинге или нет
                зарегистрированной стратегии.
        """
        strategy_id = _CONTENT_TYPE_MAPPING.get(content_type)
        if strategy_id is None:
            raise UnsupportedFormatError(content_type)
        strategy = self._strategies.get(strategy_id)
        if strategy is None:
            raise UnsupportedFormatError(content_type)
        return strategy

    def list_supported_content_types(self) -> list[str]:
        """Список content_type, для которых есть зарегистрированная стратегия."""
        return [ct for ct, sid in _CONTENT_TYPE_MAPPING.items() if sid in self._strategies]
