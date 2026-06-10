"""LLM Gateway client (T-S01-019).

Унифицированный клиент к Ollama:
- /api/generate с format=json для structured output
- Retry при невалидном JSON (max 2, см. SETUP-01 §16.3 Ретраи)
- LLMUnavailable при connection / 5xx ошибках
- Логирует metrics в LLMCallResult: model, latency_ms, attempts, tokens.

Schema validation вынесена в caller (генератор передаёт Pydantic-модель;
gateway возвращает уже-валидный экземпляр).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from schemas.common.defaults import DEFAULT_EMBEDDING_MODEL

from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class LLMCallResult:
    """Метрики одного вызова (соответствует подмножеству DTO-26 LLMResponseDTO)."""

    raw_text: str
    model_name: str
    latency_ms: int
    attempts: int
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class StructuredCallResult[T: BaseModel]:
    """Результат structured-вызова: распарсенный объект + метрики."""

    parsed: T
    call: LLMCallResult


class LLMGateway:
    """Клиент к Ollama HTTP API."""

    DEFAULT_MODEL = "llama3.2"
    DEFAULT_TIMEOUT_SECONDS = 60.0
    DEFAULT_MAX_RETRIES = 2  # SETUP-01 §16.3: max 2 retries для card generation

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url, timeout=timeout_seconds
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> LLMGateway:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def generate_text(
        self,
        *,
        prompt: str,
        model: str = DEFAULT_MODEL,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMCallResult:
        """Простой text generation без structured output."""
        return self._call_ollama(
            prompt=prompt,
            model=model,
            system=system,
            temperature=temperature,
            force_json=False,
        )

    def generate_structured[T: BaseModel](
        self,
        *,
        prompt: str,
        schema: type[T],
        model: str = DEFAULT_MODEL,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> StructuredCallResult[T]:
        """Генерирует JSON, валидирует по Pydantic-схеме.

        Делает до max_retries+1 попыток: при невалидном JSON или ValidationError
        повторяет с дополненным prompt'ом.

        Raises:
            LLMUnavailableError: connection error или 5xx.
            InvalidLLMOutputError: после всех попыток JSON не парсится / не соответствует схеме.
        """
        last_error: str | None = None
        last_raw: str | None = None
        max_attempts = self._max_retries + 1

        for attempt in range(1, max_attempts + 1):
            effective_prompt = prompt
            if last_error and attempt > 1:
                effective_prompt = (
                    f"{prompt}\n\n"
                    "Previous attempt failed schema validation with: "
                    f"{last_error}\n"
                    "Return ONLY valid JSON matching the requested schema."
                )

            result = self._call_ollama(
                prompt=effective_prompt,
                model=model,
                system=system,
                temperature=temperature,
                force_json=True,
            )
            last_raw = result.raw_text

            try:
                payload = json.loads(result.raw_text)
            except json.JSONDecodeError as exc:
                last_error = f"JSON decode error: {exc}"
                logger.warning(
                    "LLM JSON decode failed (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                continue

            try:
                parsed = schema.model_validate(payload)
            except ValidationError as exc:
                last_error = str(exc)
                logger.warning(
                    "LLM schema validation failed (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    exc.errors()[:3],
                )
                continue

            return StructuredCallResult(
                parsed=parsed,
                call=LLMCallResult(
                    raw_text=result.raw_text,
                    model_name=result.model_name,
                    latency_ms=result.latency_ms,
                    attempts=attempt,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                ),
            )

        raise InvalidLLMOutputError(
            f"LLM produced invalid output after {max_attempts} attempts",
            raw_output=last_raw,
            attempts=max_attempts,
            last_validation_error=last_error,
        )

    def generate_embedding(
        self,
        *,
        text: str,
        model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> list[float]:
        """Embedding-вектор через /api/embeddings."""
        try:
            resp = self._client.post(
                "/api/embeddings",
                json={"model": model, "prompt": text},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(
                f"Ollama embeddings call failed: {exc}"
            ) from exc

        data = resp.json()
        vector = data.get("embedding")
        if not isinstance(vector, list):
            raise InvalidLLMOutputError(
                "Embeddings response missing 'embedding' array",
                raw_output=resp.text,
            )
        return [float(x) for x in vector]

    def _call_ollama(
        self,
        *,
        prompt: str,
        model: str,
        system: str | None,
        temperature: float,
        force_json: bool,
    ) -> LLMCallResult:
        body: dict[str, object] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system is not None:
            body["system"] = system
        if force_json:
            body["format"] = "json"

        start = time.monotonic()
        try:
            resp = self._client.post("/api/generate", json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(
                f"Ollama generate call failed: {exc}"
            ) from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        data = resp.json()
        raw_text = data.get("response", "")
        return LLMCallResult(
            raw_text=raw_text,
            model_name=model,
            latency_ms=latency_ms,
            attempts=1,
            input_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
        )
