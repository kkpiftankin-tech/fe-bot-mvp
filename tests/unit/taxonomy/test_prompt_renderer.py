"""Unit-тесты ClassificationPromptRenderer (SETUP-12 / T-S12-030)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.registry import TaxonomyBitRegistryEntry

from fe_bot.taxonomy.prompt_renderer import (
    ClassificationPromptInput,
    ClassificationPromptRenderer,
    PromptTemplateNotFoundError,
)

pytestmark = pytest.mark.unit


def _entry(
    *,
    bit_index: int,
    class_slug: str,
    display_name_ru: str = "",
    description: str = "Описание класса для теста.",
    level: int = 0,
    parent_path: str = "",
) -> TaxonomyBitRegistryEntry:
    return TaxonomyBitRegistryEntry(
        version_id="v1.0.0",
        level=level,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=display_name_ru or f"Класс {class_slug}",
        description=description,
        created_at=datetime.now(tz=UTC),
    )


class TestRenderL0:
    def test_renders_with_candidates(self) -> None:
        renderer = ClassificationPromptRenderer()
        params = ClassificationPromptInput(
            level=0,
            parent_path="",
            candidates=[
                _entry(bit_index=0, class_slug="task"),
                _entry(bit_index=1, class_slug="schema"),
            ],
            section_text="Это секция про задачу.",
            free_slots_count=8,
        )
        out = renderer.render(params)
        assert "Уровень классификации: L0." in out
        # Без вышестоящих уровней — context_block пустой
        assert "Контекст вышестоящих уровней" not in out
        # Кандидаты присутствуют
        assert "[0] task" in out
        assert "[1] schema" in out
        # Hint о свободных слотах
        assert "Свободных слотов на этом уровне: 8" in out
        # Section text
        assert "Это секция про задачу." in out
        # JSON-блок присутствует
        assert '"decision":' in out

    def test_l0_empty_candidates(self) -> None:
        renderer = ClassificationPromptRenderer()
        params = ClassificationPromptInput(
            level=0,
            parent_path="",
            candidates=[],
            section_text="text",
            free_slots_count=10,
        )
        out = renderer.render(params)
        assert "на этом уровне пока нет ни одного класса" in out
        assert "(0 из 10 возможных" in out


class TestRenderL1:
    def test_l1_includes_l0_context(self) -> None:
        renderer = ClassificationPromptRenderer()
        params = ClassificationPromptInput(
            level=1,
            parent_path="task",
            candidates=[_entry(bit_index=0, class_slug="pvo")],
            section_text="Текст про ПВО",
            free_slots_count=9,
            primary_l0_slug="task",
            primary_l0_display_ru="Задача",
        )
        out = renderer.render(params)
        assert "Уровень классификации: L1." in out
        assert "L0 (основной класс) = \"task\"" in out
        assert "Задача" in out
        # Scope-suffix: " под "task""
        assert 'под "task"' in out

    def test_l1_with_multi_tag(self) -> None:
        renderer = ClassificationPromptRenderer()
        params = ClassificationPromptInput(
            level=1,
            parent_path="task",
            candidates=[],
            section_text="text",
            free_slots_count=10,
            primary_l0_slug="task",
            primary_l0_display_ru="Задача",
            also_applies_l0=["schema", "task"],  # task дублируется — должен отфильтроваться
        )
        out = renderer.render(params)
        assert "multi-tag L0" in out
        # task не должен попадать в "также применимы" (это primary)
        assert '"schema"' in out


class TestRenderL2:
    def test_l2_full_context(self) -> None:
        renderer = ClassificationPromptRenderer()
        params = ClassificationPromptInput(
            level=2,
            parent_path="task.pvo",
            candidates=[_entry(bit_index=0, class_slug="tracking")],
            section_text="Tracking text",
            free_slots_count=9,
            primary_l0_slug="task",
            primary_l1_slug="pvo",
            primary_l1_display_ru="ПВО",
        )
        out = renderer.render(params)
        assert "Уровень классификации: L2." in out
        assert "L0 (основной класс)" in out
        assert "L1 (основной подкласс) = \"pvo\"" in out


class TestValidation:
    def test_invalid_level(self) -> None:
        renderer = ClassificationPromptRenderer()
        with pytest.raises(ValueError, match="level must be"):
            renderer.render(
                ClassificationPromptInput(
                    level=5,
                    parent_path="",
                    candidates=[],
                    section_text="x",
                    free_slots_count=10,
                )
            )

    def test_l0_with_parent_rejected(self) -> None:
        renderer = ClassificationPromptRenderer()
        with pytest.raises(ValueError, match="level=0 requires empty"):
            renderer.render(
                ClassificationPromptInput(
                    level=0,
                    parent_path="task",
                    candidates=[],
                    section_text="x",
                    free_slots_count=10,
                )
            )

    def test_l1_requires_primary_l0(self) -> None:
        renderer = ClassificationPromptRenderer()
        with pytest.raises(ValueError, match="primary_l0_slug"):
            renderer.render(
                ClassificationPromptInput(
                    level=1,
                    parent_path="task",
                    candidates=[],
                    section_text="x",
                    free_slots_count=10,
                )
            )

    def test_l2_requires_dotted_parent_path(self) -> None:
        renderer = ClassificationPromptRenderer()
        with pytest.raises(ValueError, match="<l0>.<l1>"):
            renderer.render(
                ClassificationPromptInput(
                    level=2,
                    parent_path="task",
                    candidates=[],
                    section_text="x",
                    free_slots_count=10,
                    primary_l0_slug="task",
                    primary_l1_slug="pvo",
                )
            )

    def test_empty_section_text_rejected(self) -> None:
        renderer = ClassificationPromptRenderer()
        with pytest.raises(ValueError, match="section_text"):
            renderer.render(
                ClassificationPromptInput(
                    level=0,
                    parent_path="",
                    candidates=[],
                    section_text="   ",
                    free_slots_count=10,
                )
            )


class TestTemplateLoading:
    def test_missing_template(self, tmp_path: object) -> None:
        from pathlib import Path

        assert isinstance(tmp_path, Path)
        bogus = tmp_path / "missing.txt"
        renderer = ClassificationPromptRenderer(template_path=bogus)
        with pytest.raises(PromptTemplateNotFoundError):
            renderer.render(
                ClassificationPromptInput(
                    level=0,
                    parent_path="",
                    candidates=[],
                    section_text="x",
                    free_slots_count=10,
                )
            )


class TestNoOverflowMessage:
    def test_overflow_hint_shown_when_no_slots(self) -> None:
        renderer = ClassificationPromptRenderer()
        # 10 кандидатов, 0 свободных
        candidates = [
            _entry(bit_index=i, class_slug=f"slot-{i}") for i in range(10)
        ]
        params = ClassificationPromptInput(
            level=0,
            parent_path="",
            candidates=candidates,
            section_text="text",
            free_slots_count=0,
        )
        out = renderer.render(params)
        assert "Свободных слотов нет" in out
        assert "все 10 заняты" in out
