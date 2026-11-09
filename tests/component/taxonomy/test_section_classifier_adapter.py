"""Component-тесты HierarchicalSectionClassifier (SETUP-12 / T-S12-041).

Покрывает:
- ParsedSection обогащается ``classification_state``.
- Legacy ``section_type`` derive'ится из primary_l0_slug.
- ``confidence`` берётся с уровня 0.
- ``classification_method`` = "llm".
- Cascading UNKNOWN на L0 → section_type=UNKNOWN, confidence=0.
- LLM unrecoverable error пробрасывается из apply_to_sections.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from schemas.setup.parsed_section import (
    ParsedSection,
    ParsedSectionStatus,
    SectionType,
)
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)

from fe_bot.llm_gateway.client import LLMCallResult, StructuredCallResult
from fe_bot.llm_gateway.exceptions import LLMUnavailableError
from fe_bot.taxonomy import (
    AutoAllocator,
    AutoAllocatorConfig,
    EmbeddingIndex,
    HierarchicalClassifier,
    HierarchicalSectionClassifier,
    LLMClassifier,
    TaxonomyRegistry,
)
from fe_bot.taxonomy.llm_classifier import LLMClassifierError
from fe_bot.taxonomy.prompt_renderer import ClassificationPromptRenderer

pytestmark = pytest.mark.component


class _ScriptedGateway:
    def __init__(self, scripts: list[dict[str, Any]]) -> None:
        self._scripts = list(scripts)

    def generate_structured(self, **kwargs: Any) -> Any:
        if not self._scripts:
            raise AssertionError("ScriptedGateway: empty queue")
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


class _AlwaysFailGateway:
    def generate_structured(self, **_: Any) -> Any:
        raise LLMUnavailableError("connection refused")


class _NullEmbed:
    def compute(self, text: str) -> list[float]:  # noqa: ARG002
        return [0.0]


def _make_section(
    *,
    section_id: str = "sec_1",
    title: str = "Schema sensor",
    raw_text: str = "Описание секции про схему датчика.",
) -> ParsedSection:
    return ParsedSection(
        section_id=section_id,
        parse_job_id="pj_1",
        source_document_id="src_1",
        title=title,
        heading_path=[title],
        raw_text=raw_text,
        normalized_text=raw_text,
        confidence=0.5,
        created_at=datetime.now(tz=UTC),
    )


def _entry(
    *, level: int, parent_path: str, bit_index: int, class_slug: str
) -> TaxonomyBitRegistryEntry:
    return TaxonomyBitRegistryEntry(
        version_id="v1.0.0",
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=f"Класс {class_slug}",
        description=f"Описание {class_slug}.",
        created_at=datetime.now(tz=UTC),
        embedding=[1.0],
    )


def _build_pipeline(
    *,
    entries: list[TaxonomyBitRegistryEntry],
    scripts: list[dict[str, Any]],
    gateway: Any = None,
) -> tuple[HierarchicalSectionClassifier, TaxonomyRegistry]:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(
        TaxonomyVersion(
            version_id="v1.0.0",
            created_at=datetime.now(tz=UTC),
            is_active=True,
            entries=entries,
        )
    )
    gw = gateway or _ScriptedGateway(scripts)
    cfg = AutoAllocatorConfig()
    llm = LLMClassifier(
        gateway=gw,
        renderer=ClassificationPromptRenderer(),
        config=cfg,
    )
    allocator = AutoAllocator(
        registry=reg,
        embedding_index=EmbeddingIndex(_NullEmbed()),
        config=cfg,
    )
    hc = HierarchicalClassifier(
        registry=reg,
        llm_classifier=llm,
        auto_allocator=allocator,
        config=cfg,
    )
    adapter = HierarchicalSectionClassifier(
        classifier=hc, registry=reg, confidence_threshold=0.7
    )
    return adapter, reg


class TestBasicDerivation:
    def test_classifies_and_derives_legacy_fields(self) -> None:
        adapter, _reg = _build_pipeline(
            entries=[
                _entry(
                    level=0, parent_path="", bit_index=1, class_slug="schema"
                )
            ],
            scripts=[
                {
                    "decision": "existing",
                    "selected": [
                        {"bit": 1, "confidence": 0.9, "reason": "schema"}
                    ],
                    "overall_confidence": 0.9,
                    "reason": "",
                },
                # L1: пусто → unknown
                {
                    "decision": "unknown",
                    "overall_confidence": 0.1,
                    "reason": "empty",
                },
            ],
        )
        section = _make_section(title="Schema sensor")
        [classified] = adapter.apply_to_sections([section])
        assert classified.classification_state is not None
        state = classified.classification_state
        assert state.primary_l0_idx == 1
        assert state.unknown_at_level == 1  # L1 не нашёлся
        # legacy fields derived
        assert classified.section_type == SectionType.SCHEMA
        assert classified.confidence == pytest.approx(0.9)
        assert classified.section_status == ParsedSectionStatus.CLASSIFIED
        assert classified.classification_method == "llm"

    def test_unknown_l0_yields_unknown_section_type(self) -> None:
        adapter, _ = _build_pipeline(
            entries=[
                _entry(
                    level=0, parent_path="", bit_index=0, class_slug="task"
                )
            ],
            scripts=[
                {
                    "decision": "unknown",
                    "overall_confidence": 0.1,
                    "reason": "random text",
                }
            ],
        )
        section = _make_section()
        [classified] = adapter.apply_to_sections([section])
        assert classified.section_type == SectionType.UNKNOWN
        assert classified.confidence == 0.0
        assert classified.section_status == ParsedSectionStatus.LOW_CONFIDENCE
        state = classified.classification_state
        assert state is not None
        assert state.unknown_at_level == 0

    def test_low_confidence_below_threshold(self) -> None:
        # L0 OK с 0.65 — между T_SET=0.6 (бит ставится) и threshold=0.7
        # (status = LOW_CONFIDENCE). Cascading на L1 → unknown_at_level=1.
        adapter, _ = _build_pipeline(
            entries=[
                _entry(
                    level=0, parent_path="", bit_index=0, class_slug="task"
                )
            ],
            scripts=[
                {
                    "decision": "existing",
                    "selected": [{"bit": 0, "confidence": 0.65, "reason": ""}],
                    "overall_confidence": 0.65,
                    "reason": "",
                },
                {
                    "decision": "unknown",
                    "overall_confidence": 0.1,
                    "reason": "empty L1",
                },
            ],
        )
        section = _make_section()
        [classified] = adapter.apply_to_sections([section])
        assert classified.section_type == SectionType.TASK
        assert classified.confidence == pytest.approx(0.65)
        assert classified.section_status == ParsedSectionStatus.LOW_CONFIDENCE


class TestUnknownDomainProfileFallback:
    def test_process_l0_class_falls_back_to_other(self) -> None:
        """L0 slug='process' не имеет legacy SectionType — fallback OTHER."""
        adapter, _ = _build_pipeline(
            entries=[
                _entry(
                    level=0, parent_path="", bit_index=7, class_slug="process"
                )
            ],
            scripts=[
                {
                    "decision": "existing",
                    "selected": [{"bit": 7, "confidence": 0.9, "reason": ""}],
                    "overall_confidence": 0.9,
                    "reason": "",
                },
                {
                    "decision": "unknown",
                    "overall_confidence": 0.1,
                    "reason": "",
                },
            ],
        )
        section = _make_section()
        [classified] = adapter.apply_to_sections([section])
        assert classified.section_type == SectionType.OTHER


class TestErrorPropagation:
    def test_llm_unavailable_propagates(self) -> None:
        adapter, _ = _build_pipeline(
            entries=[
                _entry(
                    level=0, parent_path="", bit_index=0, class_slug="task"
                )
            ],
            scripts=[],
            gateway=_AlwaysFailGateway(),
        )
        section = _make_section()
        with pytest.raises(LLMClassifierError, match="unavailable"):
            adapter.apply_to_sections([section])


class TestBatch:
    def test_multiple_sections_classified(self) -> None:
        scripts = []
        # 3 sections × 3 LLM calls each
        for _ in range(3):
            scripts.extend(
                [
                    {
                        "decision": "existing",
                        "selected": [
                            {"bit": 0, "confidence": 0.9, "reason": ""}
                        ],
                        "overall_confidence": 0.9,
                        "reason": "",
                    },
                    {
                        "decision": "unknown",
                        "overall_confidence": 0.1,
                        "reason": "empty",
                    },
                ]
            )
        adapter, _ = _build_pipeline(
            entries=[
                _entry(
                    level=0, parent_path="", bit_index=0, class_slug="task"
                )
            ],
            scripts=scripts,
        )
        sections = [_make_section(section_id=f"sec_{i}") for i in range(3)]
        out = adapter.apply_to_sections(sections)
        assert len(out) == 3
        for s in out:
            assert s.section_type == SectionType.TASK
            assert s.classification_state is not None
