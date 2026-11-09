"""LLMGatewayEmbeddingComputer (SETUP-12 / wiring).

Адаптер, превращающий ``LLMGateway`` (с методом ``generate_embedding``)
в ``EmbeddingComputer`` Protocol, который ждёт ``EmbeddingIndex``.

Используется только в реальном wiring'е (dependencies.py); тесты
HTC компонентов работают со stub-computer'ами.

При недоступности LLM возвращает нулевой вектор фиксированной
размерности — каскада сбоев не будет, но similarity-gate перестанет
делать sensible decisions (auto-allocator проблему всё равно
обработает корректно через free-slot или force-merge).
"""

from __future__ import annotations

import logging

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)


class LLMGatewayEmbeddingComputer:
    """Адаптер LLMGateway → EmbeddingComputer."""

    def __init__(
        self,
        *,
        gateway: LLMGateway,
        model: str = "nomic-embed-text",
        dimension: int = 384,
    ) -> None:
        self._gateway = gateway
        self._model = model
        self._dimension = dimension

    def compute(self, text: str) -> list[float]:
        try:
            vector = self._gateway.generate_embedding(
                text=text, model=self._model
            )
        except (LLMUnavailableError, InvalidLLMOutputError) as exc:
            logger.warning(
                "Embedding computation failed for similarity-gate "
                "(text_len=%d): %s; returning zero vector",
                len(text),
                exc,
            )
            return [0.0] * self._dimension
        if len(vector) != self._dimension:
            logger.warning(
                "Embedding dimension mismatch: got %d, expected %d",
                len(vector),
                self._dimension,
            )
            # Defensive: подгоняем длину
            if len(vector) > self._dimension:
                return vector[: self._dimension]
            return list(vector) + [0.0] * (self._dimension - len(vector))
        return list(vector)


__all__ = ["LLMGatewayEmbeddingComputer"]
