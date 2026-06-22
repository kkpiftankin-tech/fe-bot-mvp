"""LLMCardAdapter (SETUP-05 / T-S05-019).

Тонкая обёртка над ``LLMGateway.generate_structured`` для генерации
``RAGCardDraft``. Берёт на себя:

- Трансляцию gateway-ошибок в SETUP-05 ``RAGCardGenerationErrorCode``.
- Учёт ``timeout_sec`` (gateway уже встроен; здесь — конфигурация).
- Fallback на ``RAGCardFallbackGenerator`` при недоступности LLM.
- Режим ``mode="template"`` — обходит LLM полностью.
- Метрики (model, attempts, duration).

Schema validation и repair-retry уже реализованы внутри ``LLMGateway`` (см.
src/fe_bot/llm_gateway/client.py:103-180).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from fe_bot.llm_gateway.client import LLMGateway, StructuredCallResult
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)
from fe_bot.setup.rag_card_generation.precheck import RAGCardDraft

logger = logging.getLogger(__name__)


class LLMCardGenerationFailed(Exception):
    """Ошибка генерации карточки через LLM. error_code — RAGCardGenerationErrorCode.value."""

    def __init__(self, error_code: str, reason: str) -> None:
        self.error_code = error_code
        self.reason = reason
        super().__init__(f"{error_code}: {reason}")


@dataclass(slots=True)
class LLMGenerationResult:
    """Результат генерации draft + метрики."""

    draft: RAGCardDraft
    attempts: int
    duration_ms: int
    model: str
    used_fallback: bool


class FallbackGenerator:
    """Контракт fallback-генератора (для ``mode='template'`` или при недоступности LLM).

    В MVP — простая реализация на template; продакшен может подменить на
    rule-based generator с детерминированными правилами.
    """

    def generate_draft(self, prompt: str, *, doc_type: str) -> RAGCardDraft:
        raise NotImplementedError


def _force_fallback_env() -> bool:
    return os.environ.get("FE_BOT_FORCE_FALLBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class LLMCardAdapter:
    """Адаптер над LLMGateway для генерации RAGCardDraft.

    Поддерживает три режима:
    - ``llm`` (default): вызывает LLMGateway; при недоступности → fallback (если задан).
    - ``template``: всегда использует fallback (LLM не вызывается).
    - ``hybrid`` (alias для ``llm``): резервируется для будущих policies.
    """

    def __init__(
        self,
        *,
        llm_gateway: LLMGateway,
        fallback_generator: FallbackGenerator | None = None,
        model: str = "llama3.2",
        timeout_sec: int = 60,
    ) -> None:
        self._gateway = llm_gateway
        self._fallback = fallback_generator
        self._model = model
        self._timeout_sec = timeout_sec

    @property
    def model(self) -> str:
        return self._model

    def generate(
        self,
        prompt: str,
        *,
        doc_type: str,
        mode: str = "llm",
    ) -> LLMGenerationResult:
        """Генерирует RAGCardDraft. Возвращает draft + метрики.

        Raises:
            LLMCardGenerationFailed: с ``error_code`` ∈ {LLM_GATEWAY_UNAVAILABLE,
              LLM_TIMEOUT, INVALID_LLM_OUTPUT, INVALID_GENERATION_MODE}.
        """
        if mode not in {"llm", "template", "hybrid"}:
            raise LLMCardGenerationFailed(
                "INVALID_GENERATION_MODE",
                f"Unknown generation_mode: {mode!r}",
            )

        # Template mode или global force fallback → bypass LLM.
        if mode == "template" or _force_fallback_env():
            return self._invoke_fallback(prompt, doc_type=doc_type)

        start = time.perf_counter()
        try:
            result: StructuredCallResult[RAGCardDraft] = self._gateway.generate_structured(
                prompt=prompt,
                schema=RAGCardDraft,
                model=self._model,
                temperature=0.0,
            )
        except LLMUnavailableError as exc:
            logger.warning("LLM unavailable, attempting fallback: %s", exc)
            if self._fallback is not None:
                return self._invoke_fallback(prompt, doc_type=doc_type)
            raise LLMCardGenerationFailed("LLM_GATEWAY_UNAVAILABLE", str(exc)) from exc
        except InvalidLLMOutputError as exc:
            raise LLMCardGenerationFailed("INVALID_LLM_OUTPUT", str(exc)) from exc
        except TimeoutError as exc:
            raise LLMCardGenerationFailed("LLM_TIMEOUT", str(exc)) from exc

        duration_ms = max(int((time.perf_counter() - start) * 1000), 0)
        return LLMGenerationResult(
            draft=result.parsed,
            attempts=result.call.attempts,
            duration_ms=duration_ms,
            model=result.call.model_name,
            used_fallback=False,
        )

    def _invoke_fallback(self, prompt: str, *, doc_type: str) -> LLMGenerationResult:
        if self._fallback is None:
            raise LLMCardGenerationFailed(
                "LLM_GATEWAY_UNAVAILABLE",
                "LLM unavailable and no fallback configured",
            )
        start = time.perf_counter()
        draft = self._fallback.generate_draft(prompt, doc_type=doc_type)
        duration_ms = max(int((time.perf_counter() - start) * 1000), 0)
        return LLMGenerationResult(
            draft=draft,
            attempts=1,
            duration_ms=duration_ms,
            model="fallback_template",
            used_fallback=True,
        )


# Re-export для удобства orchestrator.
__all__ = [
    "FallbackGenerator",
    "LLMCardAdapter",
    "LLMCardGenerationFailed",
    "LLMGenerationResult",
    "RAGCardDraft",
]
