"""Unit-тесты ClassifierDescriptionGenerator (SETUP-13 / ADR-HTC-09)."""

from __future__ import annotations

import pytest

from fe_bot.classifier.description_generator import ClassifierDescriptionGenerator
from fe_bot.llm_gateway.client import LLMCallResult, StructuredCallResult
from fe_bot.llm_gateway.exceptions import LLMUnavailableError

pytestmark = pytest.mark.unit


class _FakeGateway:
    def __init__(self, description: str | None = None, *, raises: Exception | None = None):
        self._description = description
        self._raises = raises
        self.last_kwargs: dict[str, object] | None = None

    def generate_structured(self, **kwargs):  # type: ignore[no-untyped-def]
        self.last_kwargs = kwargs
        if self._raises is not None:
            raise self._raises
        schema = kwargs["schema"]
        parsed = schema(description=self._description)
        return StructuredCallResult(
            parsed=parsed,
            call=LLMCallResult(raw_text="{}", model_name="fake", latency_ms=1, attempts=1),
        )


class TestGenerate:
    def test_returns_llm_description(self) -> None:
        gateway = _FakeGateway(description="Глубокая нейронная сеть — архитектура модели.")
        generator = ClassifierDescriptionGenerator(llm_gateway=gateway)  # type: ignore[arg-type]
        result = generator.generate(name="DNN", path=["АСУ", "Аналитика", "DNN"])
        assert result == "Глубокая нейронная сеть — архитектура модели."

    def test_prompt_includes_name_and_path(self) -> None:
        gateway = _FakeGateway(description="x")
        generator = ClassifierDescriptionGenerator(llm_gateway=gateway)  # type: ignore[arg-type]
        generator.generate(name="DNN", path=["АСУ", "Аналитика", "DNN"])
        prompt = gateway.last_kwargs["prompt"]
        assert "DNN" in prompt
        assert "АСУ → Аналитика → DNN" in prompt

    def test_propagates_llm_unavailable(self) -> None:
        gateway = _FakeGateway(raises=LLMUnavailableError("down"))
        generator = ClassifierDescriptionGenerator(llm_gateway=gateway)  # type: ignore[arg-type]
        with pytest.raises(LLMUnavailableError):
            generator.generate(name="DNN", path=["АСУ", "DNN"])
