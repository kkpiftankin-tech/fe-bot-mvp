"""Unit-тесты LLMCardAdapter (SETUP-05 / T-S05-019)."""

from __future__ import annotations

from typing import Any

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
    _fix_stray_escaped_newlines,
    _normalize_llm_json,
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
    """Minimal stub: возвращает заданный draft / raises.

    SETUP-05 v2 lenient path: adapter использует
    ``generate_structured`` с permissive-схемой и затем нормализует
    payload под RAGCardDraft. FakeGateway сериализует draft в payload
    и возвращает обёртку StructuredCallResult.
    """

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

    def generate_structured(self, **kwargs) -> Any:
        if self._raises is not None:
            raise self._raises
        assert self._draft is not None
        schema = kwargs.get("schema")
        payload = self._draft.model_dump()
        # Если schema — permissive (_PermissiveLLMJSON), парсим через неё.
        parsed = schema.model_validate(payload) if schema is not None else self._draft
        return StructuredCallResult(
            parsed=parsed,
            call=LLMCallResult(
                raw_text=self._draft.model_dump_json(),
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

    def test_attempts_counter(self) -> None:
        """SETUP-05 v2 lenient: retry делегирован в LLMGateway
        (generate_structured), поэтому gateway.attempts → result.attempts
        напрямую."""
        gw = _FakeGateway(draft=_draft(), attempts=3)
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        result = adapter.generate("prompt", doc_type="schema_card")
        assert result.attempts == 3
        assert result.draft.doc_id == "x.v1"


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
        # Без fallback → InvalidLLMOutputError транслируется в INVALID_LLM_OUTPUT.
        gw = _FakeGateway(raises=InvalidLLMOutputError("bad json"))
        adapter = LLMCardAdapter(llm_gateway=gw)  # type: ignore[arg-type]
        with pytest.raises(LLMCardGenerationFailed) as excinfo:
            adapter.generate("p", doc_type="schema_card")
        assert excinfo.value.error_code == "INVALID_LLM_OUTPUT"

    def test_invalid_llm_output_uses_fallback_when_configured(self) -> None:
        # С fallback → INVALID_LLM_OUTPUT не падает, fallback подставляет draft.
        gw = _FakeGateway(raises=InvalidLLMOutputError("bad json"))
        fallback = _FakeFallback()
        adapter = LLMCardAdapter(
            llm_gateway=gw,  # type: ignore[arg-type]
            fallback_generator=fallback,
        )
        result = adapter.generate("p", doc_type="schema_card")
        assert result.used_fallback is True
        assert fallback.calls == 1

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


class TestFixStrayEscapedNewlines:
    def test_literal_backslash_n_becomes_real_newline(self) -> None:
        assert _fix_stray_escaped_newlines("Входы\\nСensors") == "Входы\nСensors"

    def test_cyrillic_confused_backslash_becomes_real_newline(self) -> None:
        # Слабая модель иногда путает латинскую "n" с похожей кириллической "н".
        assert _fix_stray_escaped_newlines("Выходы\\нОпределение") == "Выходы\nОпределение"

    def test_leaves_normal_text_untouched(self) -> None:
        text = "Обычный текст без экранированных переносов."
        assert _fix_stray_escaped_newlines(text) == text


class TestNormalizeLLMJSONBodyMarkdown:
    """SETUP-05: body_markdown/title нормализуются после LLM-генерации —
    закрывает баг с литеральными "\\n"/"\\н" в реальном выводе llama3.2
    (обнаружено на mars_fe1 / Handbook of Multisensor Data Fusion)."""

    def test_stray_newlines_fixed_in_body(self) -> None:
        payload = {
            "doc_id": "x.v1",
            "doc_type": "task_card",
            "title": "X",
            "body_markdown": "## Входы\\nSensors и observations.\\нОпределение готово.",
        }
        out = _normalize_llm_json(payload, doc_type_hint="task_card")
        assert "\\n" not in out["body_markdown"]
        assert "\\н" not in out["body_markdown"]
        assert out["body_markdown"] == "## Входы\nSensors и observations.\nОпределение готово."
