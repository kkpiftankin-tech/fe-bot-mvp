"""Unit-тесты LLMClassifier (SETUP-12 / T-S12-031).

FakeGateway возвращает заданный payload через generate_structured;
проверяем все 3 ветки Decision + edge-cases нормализации.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from schemas.taxonomy.decision import DecisionKind
from schemas.taxonomy.registry import TaxonomyBitRegistryEntry

from fe_bot.llm_gateway.client import LLMCallResult, StructuredCallResult
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)
from fe_bot.taxonomy.config import AutoAllocatorConfig
from fe_bot.taxonomy.llm_classifier import (
    LLMClassifier,
    LLMClassifierError,
)
from fe_bot.taxonomy.prompt_renderer import ClassificationPromptRenderer

pytestmark = pytest.mark.unit


class _FakeGateway:
    """Stub LLMGateway: возвращает заданный payload в parsed-обёртке."""

    def __init__(
        self,
        *,
        payload: dict[str, Any] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self._payload = payload
        self._raises = raises
        self.calls: list[dict[str, Any]] = []

    def generate_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        schema = kwargs.get("schema")
        # schema — _PermissiveLLMJSON (extra=allow)
        assert schema is not None
        parsed = schema.model_validate(self._payload or {})
        return StructuredCallResult(
            parsed=parsed,
            call=LLMCallResult(
                raw_text=str(self._payload),
                model_name="llama3.2",
                latency_ms=10,
                attempts=1,
            ),
        )


def _entry(
    *,
    bit_index: int,
    class_slug: str,
    level: int = 0,
    parent_path: str = "",
) -> TaxonomyBitRegistryEntry:
    return TaxonomyBitRegistryEntry(
        version_id="v1.0.0",
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=f"Класс {class_slug}",
        description=f"Описание {class_slug} для теста.",
        created_at=datetime.now(tz=UTC),
    )


def _make_classifier(
    *, payload: dict[str, Any] | None = None, raises: Exception | None = None
) -> tuple[LLMClassifier, _FakeGateway]:
    gw = _FakeGateway(payload=payload, raises=raises)
    cls = LLMClassifier(
        gateway=gw,  # type: ignore[arg-type]
        renderer=ClassificationPromptRenderer(),
        config=AutoAllocatorConfig(),
    )
    return cls, gw


class TestExisting:
    def test_simple_existing(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.9, "reason": "ok"}
                ],
                "overall_confidence": 0.85,
                "reason": "matched task",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="some text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.EXISTING
        assert len(d.selected) == 1
        assert d.selected[0].bit == 0
        assert d.overall_confidence == 0.85

    def test_multi_bit_existing(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.9, "reason": ""},
                    {"bit": 2, "confidence": 0.7, "reason": ""},
                ],
                "overall_confidence": 0.8,
                "reason": "",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[
                _entry(bit_index=0, class_slug="task"),
                _entry(bit_index=1, class_slug="schema"),
                _entry(bit_index=2, class_slug="analytics"),
            ],
            section_text="text",
            free_slots_count=7,
        )
        assert d.kind == DecisionKind.EXISTING
        assert {s.bit for s in d.selected} == {0, 2}

    def test_invalid_bit_dropped(self) -> None:
        # LLM галлюцинирует bit=5, которого нет в candidates → дропается.
        cls, _ = _make_classifier(
            payload={
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.9, "reason": ""},
                    {"bit": 5, "confidence": 0.8, "reason": ""},  # invalid
                ],
                "overall_confidence": 0.8,
                "reason": "",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.EXISTING
        assert [s.bit for s in d.selected] == [0]

    def test_all_bits_invalid_becomes_unknown(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "existing",
                "selected": [
                    {"bit": 5, "confidence": 0.9, "reason": ""},
                    {"bit": 7, "confidence": 0.7, "reason": ""},
                ],
                "overall_confidence": 0.8,
                "reason": "",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.UNKNOWN
        assert "no valid bits" in d.reason


class TestNew:
    def test_new_class_above_threshold(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "new",
                "selected": [],
                "proposal": {
                    "name_slug": "new-class",
                    "display_name_ru": "Новый класс",
                    "display_name_en": "New class",
                    "description": "Описание нового класса для теста.",
                },
                "overall_confidence": 0.80,
                "reason": "novel pattern",
            }
        )
        d = cls.classify(
            level=1,
            parent_path="task",
            candidates=[],
            section_text="novel text",
            free_slots_count=10,
            primary_l0_slug="task",
            primary_l0_display_ru="Задача",
        )
        assert d.kind == DecisionKind.NEW
        assert d.proposal is not None
        assert d.proposal.name_slug == "new-class"
        assert d.overall_confidence == 0.80

    def test_new_below_min_conf_becomes_unknown(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "new",
                "selected": [],
                "proposal": {
                    "name_slug": "weak",
                    "display_name_ru": "Слабое предложение",
                    "display_name_en": "",
                    "description": "Слабое описание для теста.",
                },
                "overall_confidence": 0.40,  # < MIN_NEW_CLASS_CONF (0.65)
                "reason": "low conf",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[],
            section_text="text",
            free_slots_count=10,
        )
        assert d.kind == DecisionKind.UNKNOWN
        assert "below threshold" in d.reason

    def test_new_proposal_validation_fails(self) -> None:
        # Slug в UPPER → не пройдёт NewClassProposal валидацию → UNKNOWN.
        cls, _ = _make_classifier(
            payload={
                "decision": "new",
                "selected": [],
                "proposal": {
                    "name_slug": "BadSlug",
                    "display_name_ru": "x",
                    "display_name_en": "",
                    "description": "short",  # < 10 chars
                },
                "overall_confidence": 0.85,
                "reason": "",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[],
            section_text="text",
            free_slots_count=10,
        )
        assert d.kind == DecisionKind.UNKNOWN
        assert "validation failed" in d.reason

    def test_new_missing_proposal_becomes_unknown(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "new",
                "selected": [],
                "proposal": None,  # missing!
                "overall_confidence": 0.85,
                "reason": "",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[],
            section_text="text",
            free_slots_count=10,
        )
        assert d.kind == DecisionKind.UNKNOWN


class TestUnknown:
    def test_explicit_unknown(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "unknown",
                "selected": [],
                "proposal": None,
                "overall_confidence": 0.1,
                "reason": "text too generic",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="random text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.UNKNOWN
        assert d.reason == "text too generic"

    def test_unknown_decision_string(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "garbage_value",
                "overall_confidence": 0.5,
                "reason": "",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.UNKNOWN
        assert "unrecognised" in d.reason


class TestErrorHandling:
    def test_llm_unavailable_raises(self) -> None:
        cls, _ = _make_classifier(
            raises=LLMUnavailableError("connection refused")
        )
        with pytest.raises(LLMClassifierError, match="unavailable"):
            cls.classify(
                level=0,
                parent_path="",
                candidates=[_entry(bit_index=0, class_slug="task")],
                section_text="text",
                free_slots_count=9,
            )

    def test_invalid_output_becomes_unknown(self) -> None:
        cls, _ = _make_classifier(
            raises=InvalidLLMOutputError("bad json after retries")
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.UNKNOWN
        assert "invalid JSON" in d.reason

    def test_timeout_becomes_unknown(self) -> None:
        cls, _ = _make_classifier(raises=TimeoutError("60s timeout"))
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.UNKNOWN
        assert "timeout" in d.reason.lower()


class TestConfidenceClamping:
    def test_overall_clamped_to_unit_interval(self) -> None:
        cls, _ = _make_classifier(
            payload={
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 1.5, "reason": ""}],
                "overall_confidence": 2.0,
                "reason": "",
            }
        )
        d = cls.classify(
            level=0,
            parent_path="",
            candidates=[_entry(bit_index=0, class_slug="task")],
            section_text="text",
            free_slots_count=9,
        )
        assert d.kind == DecisionKind.EXISTING
        assert d.overall_confidence == 1.0
        assert d.selected[0].confidence == 1.0


class TestGatewayInteraction:
    def test_passes_model_and_temperature(self) -> None:
        cls, gw = _make_classifier(
            payload={
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "x",
            }
        )
        cls.classify(
            level=0,
            parent_path="",
            candidates=[],
            section_text="text",
            free_slots_count=10,
        )
        assert len(gw.calls) == 1
        assert gw.calls[0]["model"] == "llama3.2"
        assert gw.calls[0]["temperature"] == 0.0
