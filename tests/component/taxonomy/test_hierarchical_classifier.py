"""Component-тесты HierarchicalClassifier (SETUP-12 / T-S12-040).

Покрывает 3 happy-path и cascading-stop сценарии:
- Full path: L0+L1+L2 классификация.
- Cascading at L0: UNKNOWN → state.unknown_at_level = 0.
- Cascading at L1: UNKNOWN на L1 → unknown_at_level = 1.
- Cascading at L2: UNKNOWN на L2 → unknown_at_level = 2.
- NEW на L1 → AutoCreationRecord в state.auto_created_bits.
- Multi-class на L0 → primary = argmax, also_applies_l0 в L1 promt.
- Bit с confidence < T_SET не выставляется → cascading-stop.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)

from fe_bot.llm_gateway.client import LLMCallResult, StructuredCallResult
from fe_bot.taxonomy import (
    AutoAllocator,
    AutoAllocatorConfig,
    EmbeddingIndex,
    HierarchicalClassifier,
    LLMClassifier,
    TaxonomyRegistry,
)
from fe_bot.taxonomy.prompt_renderer import ClassificationPromptRenderer

pytestmark = pytest.mark.component


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------


class _ScriptedGateway:
    """Stub LLMGateway: для каждого вызова возвращает следующий заранее
    сконфигурированный payload по порядку."""

    def __init__(self, scripts: list[dict[str, Any]]) -> None:
        self._scripts = list(scripts)
        self.calls: list[dict[str, Any]] = []

    def generate_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self._scripts:
            raise AssertionError(
                "ScriptedGateway: ran out of pre-configured responses"
            )
        payload = self._scripts.pop(0)
        schema = kwargs["schema"]
        parsed = schema.model_validate(payload)
        return StructuredCallResult(
            parsed=parsed,
            call=LLMCallResult(
                raw_text=str(payload),
                model_name="llama3.2",
                latency_ms=10,
                attempts=1,
            ),
        )


class _NullEmbed:
    def compute(self, text: str) -> list[float]:  # noqa: ARG002
        return [0.0]


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _entry(
    *,
    level: int,
    parent_path: str,
    bit_index: int,
    class_slug: str,
    version_id: str = "v1.0.0",
) -> TaxonomyBitRegistryEntry:
    return TaxonomyBitRegistryEntry(
        version_id=version_id,
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=f"Класс {class_slug}",
        description=f"Описание {class_slug}.",
        created_at=datetime.now(tz=UTC),
        embedding=[1.0],
    )


def _build_registry(
    entries: Iterator[TaxonomyBitRegistryEntry] | list[TaxonomyBitRegistryEntry],
    *,
    version_id: str = "v1.0.0",
) -> TaxonomyRegistry:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(
        TaxonomyVersion(
            version_id=version_id,
            created_at=datetime.now(tz=UTC),
            is_active=True,
            entries=list(entries),
        )
    )
    return reg


def _build_classifier(
    *,
    registry: TaxonomyRegistry,
    scripts: list[dict[str, Any]],
    config: AutoAllocatorConfig | None = None,
) -> tuple[HierarchicalClassifier, _ScriptedGateway]:
    gw = _ScriptedGateway(scripts)
    cfg = config or AutoAllocatorConfig()
    llm = LLMClassifier(
        gateway=gw,  # type: ignore[arg-type]
        renderer=ClassificationPromptRenderer(),
        config=cfg,
    )
    allocator = AutoAllocator(
        registry=registry,
        embedding_index=EmbeddingIndex(_NullEmbed()),
        config=cfg,
    )
    hc = HierarchicalClassifier(
        registry=registry,
        llm_classifier=llm,
        auto_allocator=allocator,
        config=cfg,
    )
    return hc, gw


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


class TestFullPath:
    def test_l0_l1_l2_classifies(self) -> None:
        reg = _build_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=1,
                    parent_path="task",
                    bit_index=0,
                    class_slug="pvo",
                ),
                _entry(
                    level=2,
                    parent_path="task.pvo",
                    bit_index=0,
                    class_slug="tracking",
                ),
            ]
        )
        scripts = [
            # L0: pick bit 0 (task)
            {
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.9, "reason": "task"}
                ],
                "overall_confidence": 0.9,
                "reason": "",
            },
            # L1: pick bit 0 (pvo)
            {
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.85, "reason": "pvo"}
                ],
                "overall_confidence": 0.85,
                "reason": "",
            },
            # L2: pick bit 0 (tracking)
            {
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.8, "reason": "tracking"}
                ],
                "overall_confidence": 0.8,
                "reason": "",
            },
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        result = hc.classify(section_id="sec_1", section_text="Текст про ПВО tracking.")
        state = result.state
        assert state.unknown_at_level is None
        assert state.primary_l0_idx == 0
        assert state.primary_l1_idx == 0
        assert state.bits_at(0) == [0]
        assert state.bits_at(1) == [0]
        assert state.bits_at(2) == [0]
        assert state.depth_reached == 2
        # 3 LLM-вызова
        assert len(gw.calls) == 3
        assert len(result.decisions) == 3


class TestCascadingUnknown:
    def test_unknown_at_l0(self) -> None:
        reg = _build_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        scripts = [
            {
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "text too generic",
            }
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        result = hc.classify(section_id="sec_x", section_text="ramble")
        assert result.state.unknown_at_level == 0
        assert result.state.classification_bitmap == 0
        assert result.state.primary_l0_idx is None
        assert len(gw.calls) == 1  # cascading stop, L1/L2 не запрашиваются

    def test_unknown_at_l1(self) -> None:
        reg = _build_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        scripts = [
            # L0: task @ bit 0
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.9, "reason": ""}],
                "overall_confidence": 0.9,
                "reason": "",
            },
            # L1: unknown
            {
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "no L1 fit",
            },
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        result = hc.classify(section_id="sec_x", section_text="task text")
        assert result.state.unknown_at_level == 1
        assert result.state.primary_l0_idx == 0
        assert result.state.primary_l1_idx is None
        assert result.state.bits_at(0) == [0]
        assert result.state.bits_at(1) == []
        assert len(gw.calls) == 2

    def test_unknown_at_l2(self) -> None:
        reg = _build_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(level=1, parent_path="task", bit_index=0, class_slug="pvo"),
            ]
        )
        scripts = [
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.9, "reason": ""}],
                "overall_confidence": 0.9,
                "reason": "",
            },
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.85, "reason": ""}],
                "overall_confidence": 0.85,
                "reason": "",
            },
            {
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "no L2 fit",
            },
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        result = hc.classify(section_id="sec_x", section_text="text")
        assert result.state.unknown_at_level == 2
        assert result.state.primary_l1_idx == 0
        assert result.state.bits_at(0) == [0]
        assert result.state.bits_at(1) == [0]
        assert result.state.bits_at(2) == []
        assert len(gw.calls) == 3


class TestAutoCreate:
    def test_new_at_l1_creates_bit(self) -> None:
        reg = _build_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        scripts = [
            # L0
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.9, "reason": ""}],
                "overall_confidence": 0.9,
                "reason": "",
            },
            # L1 NEW
            {
                "decision": "new",
                "proposal": {
                    "name_slug": "navigation",
                    "display_name_ru": "Навигация",
                    "display_name_en": "Navigation",
                    "description": "Класс для задач навигации между объектами.",
                },
                "overall_confidence": 0.80,
                "reason": "novel",
            },
            # L2 unknown (нет classes под task.navigation)
            {
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "empty L2",
            },
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        result = hc.classify(section_id="sec_y", section_text="navigation text")
        state = result.state
        assert state.unknown_at_level == 2
        assert state.bits_at(0) == [0]
        assert state.bits_at(1) == [0]  # navigation получил bit 0
        # AutoCreationRecord записан
        assert len(state.auto_created_bits) == 1
        rec = state.auto_created_bits[0]
        assert rec.level == 1
        assert rec.parent_path == "task"
        assert rec.class_slug == "navigation"
        assert rec.triggered_by_section_id == "sec_y"
        # registry содержит новый класс
        new_entry = reg.find_by_slug(
            level=1, parent_path="task", class_slug="navigation"
        )
        assert new_entry is not None
        assert new_entry.bit_index == 0
        assert new_entry.auto_created is True
        # 3 LLM-вызова сделаны
        assert len(gw.calls) == 3


class TestMultiClassL0:
    def test_primary_is_argmax_and_also_applies_propagated(self) -> None:
        reg = _build_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=0, parent_path="", bit_index=1, class_slug="schema"
                ),
                _entry(
                    level=1, parent_path="task", bit_index=0, class_slug="pvo"
                ),
            ]
        )
        scripts = [
            # L0 multi: task=0.85, schema=0.70
            {
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.85, "reason": "task"},
                    {"bit": 1, "confidence": 0.70, "reason": "schema"},
                ],
                "overall_confidence": 0.85,
                "reason": "",
            },
            # L1 under task (primary)
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.8, "reason": "pvo"}],
                "overall_confidence": 0.8,
                "reason": "",
            },
            # L2 unknown
            {
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "empty",
            },
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        result = hc.classify(section_id="sec_z", section_text="text")
        state = result.state
        assert state.primary_l0_idx == 0  # task (выше confidence)
        assert sorted(state.bits_at(0)) == [0, 1]
        # L1-prompt должен содержать also_applies_l0 = ["schema"]
        assert len(gw.calls) >= 2
        l1_prompt = gw.calls[1]["prompt"]
        assert "multi-tag" in l1_prompt
        assert "schema" in l1_prompt


class TestConfidenceThreshold:
    def test_low_confidence_bit_not_set(self) -> None:
        reg = _build_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        # T_SET = 0.6 (default). LLM возвращает 0.4 → бит не выставляется,
        # cascading-stop на L0.
        scripts = [
            {
                "decision": "existing",
                "selected": [
                    {"bit": 0, "confidence": 0.4, "reason": "weak"}
                ],
                "overall_confidence": 0.4,
                "reason": "",
            }
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        result = hc.classify(section_id="sec_w", section_text="weak text")
        assert result.state.unknown_at_level == 0
        assert result.state.bits_at(0) == []
        # confidence_per_bit запись осталась, но cascading-stop её удалил
        assert "0:0" not in result.state.confidence_per_bit
        assert len(gw.calls) == 1


class TestMaxDepthLimit:
    def test_max_depth_2_stops_after_l1(self) -> None:
        cfg = AutoAllocatorConfig(max_depth=2)
        reg = _build_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=1, parent_path="task", bit_index=0, class_slug="pvo"
                ),
            ]
        )
        scripts = [
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.9, "reason": ""}],
                "overall_confidence": 0.9,
                "reason": "",
            },
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.85, "reason": ""}],
                "overall_confidence": 0.85,
                "reason": "",
            },
        ]
        hc, gw = _build_classifier(
            registry=reg, scripts=scripts, config=cfg
        )
        result = hc.classify(section_id="sec_d", section_text="text")
        assert result.state.depth_reached == 1
        # L2 НЕ запрашивался
        assert len(gw.calls) == 2
        # unknown_at_level — None (поскольку мы успешно прошли все уровни,
        # которые max_depth разрешает)
        assert result.state.unknown_at_level is None


class TestInputValidation:
    def test_empty_section_text(self) -> None:
        reg = _build_registry([])
        hc, _ = _build_classifier(registry=reg, scripts=[])
        with pytest.raises(ValueError, match="section_text"):
            hc.classify(section_id="sec", section_text="")

    def test_empty_section_id(self) -> None:
        reg = _build_registry([])
        hc, _ = _build_classifier(registry=reg, scripts=[])
        with pytest.raises(ValueError, match="section_id"):
            hc.classify(section_id="", section_text="text")


class TestPromptContextPropagation:
    def test_l0_prompt_has_no_context_block(self) -> None:
        reg = _build_registry(
            [_entry(level=0, parent_path="", bit_index=0, class_slug="task")]
        )
        scripts = [
            {
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "x",
            }
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        hc.classify(section_id="sec_a", section_text="text")
        l0_prompt = gw.calls[0]["prompt"]
        assert "Контекст вышестоящих уровней" not in l0_prompt

    def test_l2_prompt_has_l0_and_l1_context(self) -> None:
        reg = _build_registry(
            [
                _entry(level=0, parent_path="", bit_index=0, class_slug="task"),
                _entry(
                    level=1, parent_path="task", bit_index=0, class_slug="pvo"
                ),
            ]
        )
        scripts = [
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.9, "reason": ""}],
                "overall_confidence": 0.9,
                "reason": "",
            },
            {
                "decision": "existing",
                "selected": [{"bit": 0, "confidence": 0.85, "reason": ""}],
                "overall_confidence": 0.85,
                "reason": "",
            },
            {
                "decision": "unknown",
                "overall_confidence": 0.1,
                "reason": "empty",
            },
        ]
        hc, gw = _build_classifier(registry=reg, scripts=scripts)
        hc.classify(section_id="sec_a", section_text="text")
        l2_prompt = gw.calls[2]["prompt"]
        assert "L0 (основной класс) = \"task\"" in l2_prompt
        assert "L1 (основной подкласс) = \"pvo\"" in l2_prompt
