"""Unit-тесты LLMCardAdapter (SETUP-05 / T-S05-019)."""

from __future__ import annotations

import pytest

from fe_bot.llm_gateway.client import LLMCallResult, StructuredCallResult
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)
from fe_bot.setup.rag_card_generation.llm_adapter import (
    FallbackGenerator,
    LLMCardAdapter,
    LLMCardGenerationFailed,
)
from fe_bot.setup.rag_card_generation.precheck import RAGCardDraft

pytestmark = pytest.mark.unit


def _draft(doc_type: str = "schema_card") -> RAGCardDraft:
    return RAGCardDraft(
        doc_id="x.v1",
        doc_type=doc_type,
        title="X",
        body_markdown="some body text here for the card.",
        front_matter={"doc_id": "x.v1", "doc_type": doc_type},
        source_files=["x.md"],
        source_sections=["sec_001"],
        retrieval_tags=["x"],
    )


class _FakeGateway:
    """Minimal stub: возвращает заданный draft / raises."""

    def __init__(
        self,
        *,
        draft: RAGCardDraft | None = None,
        raises: Exception | None = None,
        attempts: int = 1,
    ) -> None:
        self._draft = draft
        self._raises = raises
        self._attempts = attempts

    def generate_structured(self, **_kwargs) -> StructuredCallResult[RAGCardDraft]:
        if self._raises is not None:
            raise self._raises
        assert self._draft is not None
        return StructuredCallResult(
            parsed=self._draft,
            call=LLMCallResult(
                raw_text="{}",
                model_name="llama3.2",
                latency_ms=100,
                attempts=self._attempts,
            ),
        )


class _FakeFallback(FallbackGenerator):
    def __init__(self) -> None:
        self.calls = 0

    def generate_draft(self, prompt: str, *, doc_type: str) -> RAGCardDraft:
        self.calls += 1
        return _draft(doc_type=doc_type)


class TestLLMMode:
    def test_happy_path(self) -> None:
        gw = _FakeGateway(draft=_draft())
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        result = adapter.generate("prompt", doc_type="schema_card")
        assert result.draft.doc_id == "x.v1"
        assert result.attempts == 1
        assert result.used_fallback is False
        assert result.model == "llama3.2"

    def test_extra_attempts_propagated(self) -> None:
        gw = _FakeGateway(draft=_draft(), attempts=3)
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        result = adapter.generate("prompt", doc_type="schema_card")
        assert result.attempts == 3


class TestFallbackOnUnavailable:
    def test_fallback_invoked_when_llm_unavailable(self) -> None:
        gw = _FakeGateway(raises=LLMUnavailableError("connection refused"))
        fallback = _FakeFallback()
        adapter = LLMCardAdapter(
            llm_gateway=gw,  # type: ignore[arg-type]
            fallback_generator=fallback,
        )
        result = adapter.generate("p", doc_type="schema_card")
        assert result.used_fallback
        assert result.model == "fallback_template"
        assert fallback.calls == 1

    def test_no_fallback_raises(self) -> None:
        gw = _FakeGateway(raises=LLMUnavailableError("connection refused"))
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        with pytest.raises(LLMCardGenerationFailed) as excinfo:
            adapter.generate("p", doc_type="schema_card")
        assert excinfo.value.error_code == "LLM_GATEWAY_UNAVAILABLE"


class TestErrorTranslation:
    def test_invalid_llm_output_raises_setup05_code(self) -> None:
        gw = _FakeGateway(raises=InvalidLLMOutputError("bad json"))
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        with pytest.raises(LLMCardGenerationFailed) as excinfo:
            adapter.generate("p", doc_type="schema_card")
        assert excinfo.value.error_code == "INVALID_LLM_OUTPUT"

    def test_timeout_translated(self) -> None:
        gw = _FakeGateway(raises=TimeoutError("LLM timeout"))
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        with pytest.raises(LLMCardGenerationFailed) as excinfo:
            adapter.generate("p", doc_type="schema_card")
        assert excinfo.value.error_code == "LLM_TIMEOUT"

    def test_invalid_mode_raises(self) -> None:
        gw = _FakeGateway(draft=_draft())
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        with pytest.raises(LLMCardGenerationFailed) as excinfo:
            adapter.generate("p", doc_type="schema_card", mode="invalid")
        assert excinfo.value.error_code == "INVALID_GENERATION_MODE"


class TestTemplateMode:
    def test_template_mode_bypasses_llm(self) -> None:
        gw = _FakeGateway(raises=AssertionError("LLM must not be called"))
        fallback = _FakeFallback()
        adapter = LLMCardAdapter(
            llm_gateway=gw,  # type: ignore[arg-type]
            fallback_generator=fallback,
        )
        result = adapter.generate("p", doc_type="schema_card", mode="template")
        assert result.used_fallback
        assert fallback.calls == 1

    def test_template_mode_without_fallback_raises(self) -> None:
        gw = _FakeGateway(draft=_draft())
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        with pytest.raises(LLMCardGenerationFailed) as excinfo:
            adapter.generate("p", doc_type="schema_card", mode="template")
        assert excinfo.value.error_code == "LLM_GATEWAY_UNAVAILABLE"


class TestForceFallbackEnv:
    def test_env_flag_forces_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FE_BOT_FORCE_FALLBACK", "1")
        gw = _FakeGateway(raises=AssertionError("LLM must not be called"))
        fallback = _FakeFallback()
        adapter = LLMCardAdapter(
            llm_gateway=gw,  # type: ignore[arg-type]
            fallback_generator=fallback,
        )
        result = adapter.generate("p", doc_type="schema_card")
        assert result.used_fallback
