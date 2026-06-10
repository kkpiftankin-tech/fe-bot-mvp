"""Тесты LLM Gateway с замоканной Ollama (T-S01-019)."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import BaseModel, ConfigDict

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)

pytestmark = pytest.mark.unit


class SimpleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    confidence: float


@pytest.fixture
def gateway() -> LLMGateway:
    """LLMGateway с базовым URL Ollama. respx.mock перехватывает запросы."""
    client = httpx.Client(base_url="http://localhost:11434", timeout=5.0)
    gw = LLMGateway(client=client, max_retries=2)
    yield gw
    gw.close()


def _generate_response(
    body_json: str, *, prompt_eval: int = 10, eval_count: int = 20
) -> dict:
    return {
        "model": "llama3.2",
        "response": body_json,
        "done": True,
        "prompt_eval_count": prompt_eval,
        "eval_count": eval_count,
    }


class TestGenerateText:
    @respx.mock
    def test_simple_text(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_generate_response("Hello, world!")
        )
        result = gateway.generate_text(prompt="Say hi", model="llama3.2")
        assert result.raw_text == "Hello, world!"
        assert result.model_name == "llama3.2"
        assert result.input_tokens == 10
        assert result.output_tokens == 20

    @respx.mock
    def test_network_error_raises_unavailable(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises(LLMUnavailableError):
            gateway.generate_text(prompt="x")

    @respx.mock
    def test_http_500_raises_unavailable(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(status_code=500)
        with pytest.raises(LLMUnavailableError):
            gateway.generate_text(prompt="x")


class TestGenerateStructured:
    @respx.mock
    def test_valid_json_first_try(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_generate_response('{"title": "Hello", "confidence": 0.9}')
        )
        result = gateway.generate_structured(prompt="x", schema=SimpleOutput)
        assert result.parsed.title == "Hello"
        assert result.parsed.confidence == 0.9
        assert result.call.attempts == 1

    @respx.mock
    def test_retry_on_invalid_json(self, gateway: LLMGateway) -> None:
        route = respx.post("http://localhost:11434/api/generate")
        route.side_effect = [
            httpx.Response(200, json=_generate_response("not a json")),
            httpx.Response(
                200,
                json=_generate_response('{"title": "OK", "confidence": 0.5}'),
            ),
        ]
        result = gateway.generate_structured(prompt="x", schema=SimpleOutput)
        assert result.parsed.title == "OK"
        assert result.call.attempts == 2

    @respx.mock
    def test_retry_on_schema_validation_error(self, gateway: LLMGateway) -> None:
        route = respx.post("http://localhost:11434/api/generate")
        route.side_effect = [
            httpx.Response(200, json=_generate_response('{"title": "x"}')),
            httpx.Response(
                200,
                json=_generate_response('{"title": "y", "confidence": 0.7}'),
            ),
        ]
        result = gateway.generate_structured(prompt="x", schema=SimpleOutput)
        assert result.parsed.confidence == 0.7
        assert result.call.attempts == 2

    @respx.mock
    def test_exhausts_retries_and_raises(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_generate_response("never valid")
        )
        with pytest.raises(InvalidLLMOutputError) as exc:
            gateway.generate_structured(prompt="x", schema=SimpleOutput)
        # max_retries=2 → 3 attempts (1 initial + 2 retries)
        assert exc.value.attempts == 3
        assert exc.value.last_validation_error is not None
        assert exc.value.raw_output == "never valid"

    @respx.mock
    def test_extra_fields_rejected(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_generate_response(
                '{"title": "x", "confidence": 0.5, "hallucinated": true}'
            )
        )
        with pytest.raises(InvalidLLMOutputError):
            gateway.generate_structured(prompt="x", schema=SimpleOutput)


class TestEmbeddings:
    @respx.mock
    def test_embedding_returns_vector(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json={"embedding": [0.1, 0.2, 0.3]}
        )
        vector = gateway.generate_embedding(text="hello")
        assert vector == [0.1, 0.2, 0.3]

    @respx.mock
    def test_embedding_network_error(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").mock(
            side_effect=httpx.ConnectError("down")
        )
        with pytest.raises(LLMUnavailableError):
            gateway.generate_embedding(text="x")

    @respx.mock
    def test_embedding_missing_field(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/embeddings").respond(
            json={"wrong": "shape"}
        )
        with pytest.raises(InvalidLLMOutputError):
            gateway.generate_embedding(text="x")
