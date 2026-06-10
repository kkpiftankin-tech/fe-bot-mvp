"""Тесты structured logging (T-S01-050)."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from fe_bot.observability.logging_config import (
    JSONFormatter,
    clear_request_context,
    get_correlation_id,
    set_correlation_id,
    with_request_context,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def logger_with_buffer() -> tuple[logging.Logger, StringIO]:
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("test.structured")
    # Очистка предыдущих handlers (изоляция тестов).
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    yield logger, buf
    set_correlation_id(None)
    clear_request_context()


class TestJSONFormatter:
    def test_basic_fields(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        logger.info("hello world")
        record = json.loads(buf.getvalue().strip())
        assert record["message"] == "hello world"
        assert record["level"] == "INFO"
        assert record["logger"] == "test.structured"
        assert "timestamp" in record

    def test_extra_fields_attached(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        logger.info("with extras", extra={"setup_job_id": "j1", "foo": 42})
        record = json.loads(buf.getvalue().strip())
        assert record["setup_job_id"] == "j1"
        assert record["foo"] == 42

    def test_correlation_id_attached(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        set_correlation_id("req_abc")
        logger.info("hello")
        record = json.loads(buf.getvalue().strip())
        assert record["correlation_id"] == "req_abc"

    def test_request_context_attached(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        with_request_context(user_id="u1", setup_job_id="j1")
        logger.info("hello")
        record = json.loads(buf.getvalue().strip())
        assert record["user_id"] == "u1"
        assert record["setup_job_id"] == "j1"

    def test_exception_serialized(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("crashed")
        record = json.loads(buf.getvalue().strip())
        assert "exception" in record
        assert "ValueError" in record["exception"]

    def test_non_json_safe_value_converted_to_str(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        # Объект с custom __str__ — не сериализуется напрямую.
        class _Custom:
            def __repr__(self) -> str:
                return "Custom(x)"

        logger.info("test", extra={"obj": _Custom()})
        record = json.loads(buf.getvalue().strip())
        assert "Custom(x)" in record["obj"]


class TestContextVars:
    def test_correlation_id_isolation(self) -> None:
        set_correlation_id("r1")
        assert get_correlation_id() == "r1"
        set_correlation_id(None)
        assert get_correlation_id() is None

    def test_request_context_accumulates(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        with_request_context(user_id="u1")
        with_request_context(setup_job_id="j1")
        logger.info("hello")
        record = json.loads(buf.getvalue().strip())
        # Оба поля сохранились.
        assert record["user_id"] == "u1"
        assert record["setup_job_id"] == "j1"

    def test_clear_request_context(
        self, logger_with_buffer: tuple[logging.Logger, StringIO]
    ) -> None:
        logger, buf = logger_with_buffer
        with_request_context(user_id="u1")
        clear_request_context()
        logger.info("hello")
        record = json.loads(buf.getvalue().strip())
        assert "user_id" not in record
