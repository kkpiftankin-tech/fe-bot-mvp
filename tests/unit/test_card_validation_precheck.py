"""Unit-тесты CardValidationPrecheck (SETUP-05 / T-S05-018)."""

from __future__ import annotations

import pytest

from fe_bot.setup.rag_card_generation.precheck import (
    CardValidationPrecheck,
    RAGCardDraft,
)

pytestmark = pytest.mark.unit


def _valid_draft(**overrides: object) -> RAGCardDraft:
    kwargs: dict[str, object] = {
        "doc_id": "analytics.sensor.v1",
        "doc_type": "analytics_card",
        "title": "Sensor analytics",
        "body_markdown": "# Sensor analytics\n\nDescription of the card body here.",
        "front_matter": {
            "doc_id": "analytics.sensor.v1",
            "doc_type": "analytics_card",
            "domain": ["naval"],
            "phase": ["feature_synthesis"],
        },
        "source_files": ["analytics.md"],
        "source_sections": ["sec_005"],
        "retrieval_tags": ["sensor", "uptime"],
    }
    kwargs.update(overrides)
    return RAGCardDraft(**kwargs)


@pytest.fixture
def precheck() -> CardValidationPrecheck:
    return CardValidationPrecheck()


class TestHappyPath:
    def test_valid_draft_passes(self, precheck: CardValidationPrecheck) -> None:
        report = precheck.check(_valid_draft())
        assert report.passed
        assert report.errors == []
        assert report.warnings == []


class TestBlockingErrors:
    def test_doc_type_invalid(self, precheck: CardValidationPrecheck) -> None:
        # Pydantic min_length=1 пройдёт; enum проверка — наша.
        report = precheck.check(_valid_draft(doc_type="ontology_card"))
        assert not report.passed
        codes = [e["code"] for e in report.errors]
        assert "DOC_TYPE_INVALID" in codes

    def test_source_files_empty(self, precheck: CardValidationPrecheck) -> None:
        report = precheck.check(_valid_draft(source_files=[]))
        assert not report.passed
        assert "SOURCE_FILES_EMPTY" in [e["code"] for e in report.errors]

    def test_source_sections_empty(self, precheck: CardValidationPrecheck) -> None:
        report = precheck.check(_valid_draft(source_sections=[]))
        assert not report.passed
        assert "SOURCE_SECTIONS_EMPTY" in [e["code"] for e in report.errors]

    def test_body_too_short(self, precheck: CardValidationPrecheck) -> None:
        # body_markdown проходит pydantic min_length=1, но precheck требует >= 20.
        report = precheck.check(_valid_draft(body_markdown="hi"))
        assert not report.passed
        assert "CARD_BODY_EMPTY" in [e["code"] for e in report.errors]

    def test_front_matter_missing_required(self, precheck: CardValidationPrecheck) -> None:
        report = precheck.check(_valid_draft(front_matter={"only_doc_id": "x"}))
        assert not report.passed
        assert "FRONT_MATTER_INVALID" in [e["code"] for e in report.errors]

    def test_placeholder_echo_detected(self, precheck: CardValidationPrecheck) -> None:
        # Слабая модель скопировала prompt-инструкцию вместо реального контента
        # (обнаружено на mars_fe1 / Handbook of Multisensor Data Fusion):
        # body_markdown-структура в prompts/rag_card/*.txt задана через
        # "<one paragraph describing...>"-плейсхолдеры.
        body = (
            "# X\n\n## Определение\n"
            "<one or two sentences defining what this field represents in the domain context>"
        )
        report = precheck.check(_valid_draft(body_markdown=body))
        assert not report.passed
        assert "CARD_BODY_PLACEHOLDER_ECHO" in [e["code"] for e in report.errors]

    def test_real_content_with_angle_brackets_is_not_flagged(
        self, precheck: CardValidationPrecheck
    ) -> None:
        # Короткие/нетекстовые угловые скобки — не проблема, нужно 3+ слова.
        body = "# X\n\n## Описание\nСм. <Table 1.2> и диапазон <0.5>."
        report = precheck.check(_valid_draft(body_markdown=body))
        assert report.passed


class TestWarnings:
    def test_retrieval_tags_empty_warning(self, precheck: CardValidationPrecheck) -> None:
        report = precheck.check(_valid_draft(retrieval_tags=[]))
        # Не блокирует генерацию.
        assert report.passed
        assert "RETRIEVAL_TAGS_EMPTY" in [w["code"] for w in report.warnings]

    def test_missing_optional_metadata_warning(self, precheck: CardValidationPrecheck) -> None:
        report = precheck.check(
            _valid_draft(
                front_matter={
                    "doc_id": "analytics.sensor.v1",
                    "doc_type": "analytics_card",
                    # domain & phase отсутствуют.
                },
            )
        )
        assert report.passed
        assert "MISSING_OPTIONAL_METADATA" in [w["code"] for w in report.warnings]


class TestMultipleErrors:
    def test_multiple_blocking_errors_accumulated(self, precheck: CardValidationPrecheck) -> None:
        report = precheck.check(
            _valid_draft(
                doc_type="ontology_card",
                source_files=[],
                source_sections=[],
                body_markdown="x",
                front_matter={},
            )
        )
        assert not report.passed
        codes = {e["code"] for e in report.errors}
        assert codes == {
            "DOC_TYPE_INVALID",
            "SOURCE_FILES_EMPTY",
            "SOURCE_SECTIONS_EMPTY",
            "CARD_BODY_EMPTY",
            "FRONT_MATTER_INVALID",
        }
