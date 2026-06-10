"""Component-тесты RAG Card Generator + Fallback (T-S01-020, T-S01-021)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
import respx
from schemas.rag.ontology import DocType
from schemas.rag.rag_card import CardStatus
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.llm_gateway.exceptions import InvalidLLMOutputError, LLMUnavailableError
from fe_bot.setup.card_generator.service import (
    HIGH_CONFIDENCE_THRESHOLD,
    RAGCardFallbackGenerator,
    RAGCardGenerator,
)

pytestmark = pytest.mark.component


def _make_section(
    *, section_type: SectionType = SectionType.ANALYTICS, title: str = "Sensor analytics T"
) -> ParsedSection:
    return ParsedSection(
        section_id="sec_1",
        source_document_id="src_1",
        setup_job_id="setup_1",
        title=title,
        section_path=["Doc"],
        section_type=section_type,
        raw_text="Sensor analytics body text.",
        normalized_text="sensor analytics body text",
        confidence=0.9,
        created_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
    )


def _valid_draft_json(*, confidence: float = 0.85, level: str = "high") -> str:
    return json.dumps(
        {
            "doc_type": "analytics_card",
            "title": "Sensor analytics feature table",
            "summary": "Аналитика эффективности сенсоров",
            "body_markdown": "## Поля\n- uptime_ratio_T\n- detection_probability_T",
            "domain": ["naval"],
            "task_type": ["classification"],
            "data_source": ["radar"],
            "entity_type": ["sensor"],
            "phase": ["feature_synthesis"],
            "agent_targets": ["FeatureSynthesisAgent"],
            "required_input_fields": ["sensor_id"],
            "output_fields": ["uptime_ratio_T"],
            "retrieval_tags": ["sensor analytics", "feature store"],
            "confidence_level": level,
            "confidence": confidence,
        }
    )


def _ollama_response(body: str) -> dict:
    return {"model": "llama3.2", "response": body, "done": True}


@pytest.fixture
def gateway() -> LLMGateway:
    client = httpx.Client(base_url="http://localhost:11434", timeout=5.0)
    gw = LLMGateway(client=client, max_retries=1)
    yield gw
    gw.close()


class TestHappyPath:
    @respx.mock
    def test_high_confidence_card_is_generated(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_ollama_response(_valid_draft_json(confidence=0.9, level="high"))
        )
        gen = RAGCardGenerator(llm_gateway=gateway)
        result = gen.generate(_make_section())

        assert result.used_fallback is False
        assert result.card.status == CardStatus.GENERATED
        assert result.card.doc_id.startswith("analytics_card.sensor_analytics_feature_table")
        assert result.card.doc_id.endswith(".v1")
        assert result.card.doc_type == DocType.ANALYTICS_CARD
        assert result.metadata.doc_id == result.card.doc_id
        assert "sensor analytics" in result.metadata.retrieval_tags

    @respx.mock
    def test_card_body_includes_title_summary_and_body(
        self, gateway: LLMGateway
    ) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_ollama_response(_valid_draft_json())
        )
        gen = RAGCardGenerator(llm_gateway=gateway)
        result = gen.generate(_make_section())
        body = result.card.body_markdown
        assert body.startswith("# Sensor analytics feature table")
        assert "Аналитика эффективности сенсоров" in body
        assert "uptime_ratio_T" in body


class TestLowConfidenceTriggersReview:
    @respx.mock
    def test_low_numeric_confidence_review_required(
        self, gateway: LLMGateway
    ) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_ollama_response(
                _valid_draft_json(confidence=HIGH_CONFIDENCE_THRESHOLD - 0.1, level="high")
            )
        )
        gen = RAGCardGenerator(llm_gateway=gateway)
        result = gen.generate(_make_section())
        assert result.card.status == CardStatus.REVIEW_REQUIRED

    @respx.mock
    def test_medium_level_review_required(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_ollama_response(_valid_draft_json(confidence=0.95, level="medium"))
        )
        gen = RAGCardGenerator(llm_gateway=gateway)
        result = gen.generate(_make_section())
        assert result.card.status == CardStatus.REVIEW_REQUIRED


class TestLLMFailureFallback:
    @respx.mock
    def test_llm_unavailable_with_fallback(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").mock(
            side_effect=httpx.ConnectError("down")
        )
        gen = RAGCardGenerator(
            llm_gateway=gateway,
            fallback_generator=RAGCardFallbackGenerator(),
        )
        result = gen.generate(_make_section())
        assert result.used_fallback is True
        assert result.card.status == CardStatus.REVIEW_REQUIRED  # low confidence
        # fallback использует эвристику section_type → doc_type.
        assert result.card.doc_type == DocType.ANALYTICS_CARD

    @respx.mock
    def test_llm_invalid_after_retries_with_fallback(
        self, gateway: LLMGateway
    ) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_ollama_response("garbage")
        )
        gen = RAGCardGenerator(
            llm_gateway=gateway,
            fallback_generator=RAGCardFallbackGenerator(),
        )
        result = gen.generate(_make_section())
        assert result.used_fallback is True

    @respx.mock
    def test_llm_unavailable_without_fallback_raises(
        self, gateway: LLMGateway
    ) -> None:
        respx.post("http://localhost:11434/api/generate").mock(
            side_effect=httpx.ConnectError("down")
        )
        gen = RAGCardGenerator(llm_gateway=gateway, fallback_generator=None)
        with pytest.raises(LLMUnavailableError):
            gen.generate(_make_section())

    @respx.mock
    def test_invalid_output_without_fallback_raises(
        self, gateway: LLMGateway
    ) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_ollama_response("not json at all")
        )
        gen = RAGCardGenerator(llm_gateway=gateway, fallback_generator=None)
        with pytest.raises(InvalidLLMOutputError):
            gen.generate(_make_section())


class TestFallbackDirectly:
    def test_fallback_uses_section_type_heuristic(self) -> None:
        fb = RAGCardFallbackGenerator()
        cases = [
            (SectionType.TASK, DocType.TASK_CARD),
            (SectionType.SCHEMA, DocType.SCHEMA_CARD),
            (SectionType.ANALYTICS, DocType.ANALYTICS_CARD),
            (SectionType.VALIDATION, DocType.VALIDATION_RULE_CARD),
            (SectionType.GLOSSARY, DocType.GLOSSARY_TERM),
            (SectionType.DOMAIN_PROFILE, DocType.DOMAIN_PROFILE),
            (SectionType.OTHER, DocType.EXAMPLE_CARD),
        ]
        for st, expected_dt in cases:
            result = fb.generate(_make_section(section_type=st, title="title"))
            assert result.card.doc_type == expected_dt, f"failed for {st}"

    def test_fallback_marks_review_required(self) -> None:
        fb = RAGCardFallbackGenerator()
        result = fb.generate(_make_section())
        assert result.card.status == CardStatus.REVIEW_REQUIRED
        assert result.used_fallback is True
        assert result.attempts == 0

    def test_fallback_includes_section_text_in_body(self) -> None:
        fb = RAGCardFallbackGenerator()
        result = fb.generate(_make_section())
        assert "sensor analytics body text" in result.card.body_markdown

    def test_fallback_has_at_least_one_tag(self) -> None:
        fb = RAGCardFallbackGenerator()
        result = fb.generate(_make_section(title="X"))  # title без значимых слов
        assert len(result.metadata.retrieval_tags) >= 1


class TestGenerateMany:
    @respx.mock
    def test_generate_many(self, gateway: LLMGateway) -> None:
        respx.post("http://localhost:11434/api/generate").respond(
            json=_ollama_response(_valid_draft_json())
        )
        gen = RAGCardGenerator(llm_gateway=gateway)
        sections = [_make_section(title=f"T-{i}") for i in range(3)]
        results = gen.generate_many(sections)
        assert len(results) == 3
        # Title в _valid_draft_json фиксирован => doc_ids могут совпасть.
        # Этот тест не проверяет уникальность, только то, что вызов на N секциях
        # отдаёт N результатов.
        assert all(r.card.doc_type == DocType.ANALYTICS_CARD for r in results)
