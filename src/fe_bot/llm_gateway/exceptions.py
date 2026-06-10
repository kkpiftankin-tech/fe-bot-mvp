"""Ошибки LLM Gateway."""

from __future__ import annotations


class LLMError(Exception):
    """Базовая ошибка LLM Gateway."""


class LLMUnavailableError(LLMError):
    """Ollama / модель недоступна (см. LLM_UNAVAILABLE §18.2 SETUP-01)."""


class InvalidLLMOutputError(LLMError):
    """LLM вернула валидный JSON, но он не соответствует ожидаемой схеме.

    После N retry эта ошибка пробрасывается наверх (caller решает: fallback или fail).
    """

    def __init__(
        self,
        message: str,
        *,
        raw_output: str | None = None,
        attempts: int = 1,
        last_validation_error: str | None = None,
    ) -> None:
        self.raw_output = raw_output
        self.attempts = attempts
        self.last_validation_error = last_validation_error
        super().__init__(message)
