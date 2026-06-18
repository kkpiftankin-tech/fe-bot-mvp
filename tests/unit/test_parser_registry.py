"""Unit-тесты ParserRegistry (T-S04-010)."""

from __future__ import annotations

import pytest
from schemas.setup.parse_job import ParserStrategy as ParserStrategyEnum
from schemas.setup.parsed_section import ParsedSection

from fe_bot.setup.parser.registry import (
    ParserRegistry,
    ParserStrategy,
    UnsupportedFormatError,
)

pytestmark = pytest.mark.unit


class _StubStrategy:
    """Fake стратегия для тестов registry."""

    def parse(
        self,
        *,
        data: bytes,
        source_document_id: str,
        parse_job_id: str,
        filename: str,
    ) -> list[ParsedSection]:
        return []


class TestRegistration:
    def test_register_and_get(self) -> None:
        reg = ParserRegistry()
        strat: ParserStrategy = _StubStrategy()
        reg.register(ParserStrategyEnum.MARKDOWN, strat)
        assert reg.get_strategy("text/markdown") is strat

    def test_unknown_content_type_raises(self) -> None:
        reg = ParserRegistry()
        with pytest.raises(UnsupportedFormatError):
            reg.get_strategy("image/png")

    def test_known_content_type_without_strategy_raises(self) -> None:
        """text/markdown в маппинге, но стратегия не зарегистрирована."""
        reg = ParserRegistry()
        with pytest.raises(UnsupportedFormatError):
            reg.get_strategy("text/markdown")

    def test_override_strategy(self) -> None:
        reg = ParserRegistry()
        first: ParserStrategy = _StubStrategy()
        second: ParserStrategy = _StubStrategy()
        reg.register(ParserStrategyEnum.MARKDOWN, first)
        reg.register(ParserStrategyEnum.MARKDOWN, second)
        assert reg.get_strategy("text/markdown") is second


class TestListSupported:
    def test_empty_registry(self) -> None:
        assert ParserRegistry().list_supported_content_types() == []

    def test_after_registration(self) -> None:
        reg = ParserRegistry()
        reg.register(ParserStrategyEnum.MARKDOWN, _StubStrategy())
        reg.register(ParserStrategyEnum.JSON, _StubStrategy())
        supported = set(reg.list_supported_content_types())
        assert "text/markdown" in supported
        assert "application/json" in supported
