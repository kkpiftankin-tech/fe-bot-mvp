"""Component-тесты AutoAllocator (SETUP-12 / T-S12-020).

Покрывает все 5 веток allocation:
- SLUG_MATCH — идемпотентность по name_slug.
- SIMILARITY_REUSE — высокая cosine >= SIM_REUSE.
- AUTO_CREATE — низкая cosine + есть свободный slot.
- FORCE_MERGE — все 10 слотов заняты, ближайший >= SIM_FORCE_MERGE.
- CLASS_OVERFLOW — все слоты заняты, никто не похож.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from schemas.taxonomy.decision import NewClassProposal
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyVersion,
)

from fe_bot.taxonomy import (
    AllocationSource,
    AutoAllocator,
    AutoAllocatorConfig,
    EmbeddingIndex,
    TaxonomyRegistry,
)

pytestmark = pytest.mark.component


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


class _StubComputer:
    """Embedding-stub: текст → вектор по словарю; иначе нулевой."""

    def __init__(self, table: dict[str, list[float]] | None = None) -> None:
        self._table = table or {}
        self.calls: list[str] = []

    def compute(self, text: str) -> list[float]:
        self.calls.append(text)
        return list(self._table.get(text, [0.0, 0.0, 0.0]))


def _make_registry(version_id: str = "v1.0.0") -> TaxonomyRegistry:
    reg = TaxonomyRegistry()
    reg.bootstrap_from_version(
        TaxonomyVersion(
            version_id=version_id,
            created_at=datetime.now(tz=UTC),
            is_active=True,
            entries=[],
        )
    )
    return reg


def _add_l1_entry(
    reg: TaxonomyRegistry,
    *,
    parent_path: str,
    bit_index: int,
    class_slug: str,
    embedding: list[float] | None = None,
    version_id: str = "v1.0.0",
) -> TaxonomyBitRegistryEntry:
    entry = TaxonomyBitRegistryEntry(
        version_id=version_id,
        level=1,
        parent_path=parent_path,
        bit_index=bit_index,
        class_slug=class_slug,
        display_name_ru=f"Класс {class_slug}",
        description=f"Описание класса {class_slug}.",
        created_at=datetime.now(tz=UTC),
        embedding=embedding,
    )
    reg.create_entry(entry)
    return entry


def _proposal(
    *,
    name_slug: str = "new-class",
    display_name_ru: str = "Новый класс",
    description: str = "Описание нового класса для теста.",
) -> NewClassProposal:
    return NewClassProposal(
        name_slug=name_slug,
        display_name_ru=display_name_ru,
        display_name_en="New class",
        description=description,
    )


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


class TestSlugMatch:
    def test_existing_slug_returns_slug_match(self) -> None:
        reg = _make_registry()
        _add_l1_entry(reg, parent_path="task", bit_index=2, class_slug="pvo")
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(_StubComputer()),
            config=AutoAllocatorConfig(),
        )
        result = allocator.allocate(
            _proposal(name_slug="pvo"),
            level=1,
            parent_path="task",
            triggered_by_section_id="sec_x",
        )
        assert result.source == AllocationSource.SLUG_MATCH
        assert result.bit_index == 2
        assert result.target_entry.class_slug == "pvo"
        assert result.auto_creation_record is None


class TestSimilarityReuse:
    def test_high_similarity_reuses(self) -> None:
        reg = _make_registry()
        # neighbour с identical embedding'ом
        neighbour_vec = [1.0, 0.0, 0.0]
        _add_l1_entry(
            reg,
            parent_path="task",
            bit_index=0,
            class_slug="pvo",
            embedding=neighbour_vec,
        )
        # proposal будет иметь тот же embedding (через stub-таблицу)
        new_text = "Новый класс Описание нового класса для теста."
        stub = _StubComputer({new_text: neighbour_vec})
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(stub),
            config=AutoAllocatorConfig(),
        )
        result = allocator.allocate(
            _proposal(),
            level=1,
            parent_path="task",
            triggered_by_section_id="sec_x",
        )
        assert result.source == AllocationSource.SIMILARITY_REUSE
        assert result.bit_index == 0
        assert result.target_entry.class_slug == "pvo"
        assert result.similarity_to_closest == pytest.approx(1.0)


class TestAutoCreate:
    def test_creates_new_bit_when_free_slot(self) -> None:
        reg = _make_registry()
        # neighbour с ортогональным embedding'ом
        _add_l1_entry(
            reg,
            parent_path="task",
            bit_index=0,
            class_slug="pvo",
            embedding=[1.0, 0.0, 0.0],
        )
        new_text = "Навигация Описание нового класса навигации."
        stub = _StubComputer({new_text: [0.0, 1.0, 0.0]})
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(stub),
            config=AutoAllocatorConfig(),
        )
        result = allocator.allocate(
            _proposal(
                name_slug="navigation",
                display_name_ru="Навигация",
                description="Описание нового класса навигации.",
            ),
            level=1,
            parent_path="task",
            triggered_by_section_id="sec_x",
        )
        assert result.source == AllocationSource.AUTO_CREATE
        assert result.bit_index == 1  # следующий свободный
        assert result.target_entry.class_slug == "navigation"
        assert result.target_entry.auto_created is True
        assert result.target_entry.created_by_section == "sec_x"
        assert result.auto_creation_record is not None
        assert result.auto_creation_record.bit_index == 1
        assert result.auto_creation_record.closest_existing_slug == "pvo"

    def test_creates_first_class_no_neighbours(self) -> None:
        reg = _make_registry()
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(_StubComputer()),
            config=AutoAllocatorConfig(),
        )
        result = allocator.allocate(
            _proposal(name_slug="first"),
            level=1,
            parent_path="task",
            triggered_by_section_id="sec_x",
        )
        assert result.source == AllocationSource.AUTO_CREATE
        assert result.bit_index == 0
        assert result.similarity_to_closest is None
        assert result.closest_existing_slug is None


class TestOverflow:
    def _fill_all_slots(
        self, reg: TaxonomyRegistry, *, parent_path: str
    ) -> None:
        for i in range(10):
            _add_l1_entry(
                reg,
                parent_path=parent_path,
                bit_index=i,
                class_slug=f"existing-{i}",
                embedding=[1.0 if j == i else 0.0 for j in range(10)],
            )

    def test_force_merge_when_moderately_similar(self) -> None:
        reg = _make_registry()
        self._fill_all_slots(reg, parent_path="task")
        # Новое предложение похоже на existing-3 на ~0.75
        new_text = "Похожий класс Описание похожего класса для теста."
        new_vec = [0.0, 0.0, 0.0, 1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0]
        # Note: cosine с [0,0,0,1,0,0,0,0,0,0] = 1/sqrt(1+0.25) = ~0.894
        # Чтобы попасть в SIM_FORCE_MERGE [0.70, 0.85), нужен другой вектор.
        # Возьмём [0, 0, 0, 1, 1, 0, 0, 0, 0, 0] vs [0,0,0,1,0,...] = 1/sqrt(2) = ~0.707
        new_vec = [0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        stub = _StubComputer({new_text: new_vec})
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(stub),
            config=AutoAllocatorConfig(),
        )
        result = allocator.allocate(
            _proposal(
                name_slug="similar",
                display_name_ru="Похожий класс",
                description="Описание похожего класса для теста.",
            ),
            level=1,
            parent_path="task",
            triggered_by_section_id="sec_x",
        )
        assert result.source == AllocationSource.FORCE_MERGE
        assert result.target_entry.class_slug == "existing-3"
        assert result.bit_index == 3
        assert result.warning_message is not None
        assert "force_merge" in result.warning_message

class TestOverflowOverflow:
    def test_class_overflow_with_low_sim(self) -> None:
        """Точный CLASS_OVERFLOW: все 10 слотов с ортогональными embedding'ами,
        новый proposal — лёгкое смещение, дающее cosine < SIM_FORCE_MERGE."""
        reg = _make_registry()
        # 10 классов, каждый — unit vector по своей оси.
        # Используем 11-мерный embedding'и, чтобы новый сохранил
        # частичную, но низкую similarity ко всем.
        for i in range(10):
            vec = [0.0] * 11
            vec[i] = 1.0
            _add_l1_entry(
                reg,
                parent_path="task",
                bit_index=i,
                class_slug=f"slot-{i}",
                embedding=vec,
            )
        # Новый proposal: вектор с весом 1.0 в 11-й оси (не пересекается).
        # cos со всеми = 0 < SIM_FORCE_MERGE → CLASS_OVERFLOW.
        new_text = (
            "Совершенно новая ось Описание совершенно новой ортогональной оси."
        )
        new_vec = [0.0] * 10 + [1.0]
        stub = _StubComputer({new_text: new_vec})
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(stub),
            config=AutoAllocatorConfig(),
        )
        result = allocator.allocate(
            NewClassProposal(
                name_slug="orthogonal",
                display_name_ru="Совершенно новая ось",
                display_name_en="",
                description="Описание совершенно новой ортогональной оси.",
            ),
            level=1,
            parent_path="task",
            triggered_by_section_id="sec_x",
        )
        assert result.source == AllocationSource.CLASS_OVERFLOW
        assert result.bit_index in {b for b in range(10)}
        assert result.warning_message is not None
        assert "class_overflow" in result.warning_message
        assert result.similarity_to_closest == pytest.approx(0.0)


class TestSeedEmbeddingLazyCompute:
    def test_seed_entry_without_embedding_gets_computed(self) -> None:
        reg = _make_registry()
        # Seed-классы обычно без embedding'а.
        _add_l1_entry(
            reg, parent_path="task", bit_index=0, class_slug="pvo", embedding=None
        )
        new_text = "Навигация Описание навигации."
        stub = _StubComputer(
            {
                "Класс pvo Описание класса pvo.": [1.0, 0.0, 0.0],
                new_text: [0.0, 1.0, 0.0],
            }
        )
        allocator = AutoAllocator(
            registry=reg,
            embedding_index=EmbeddingIndex(stub),
            config=AutoAllocatorConfig(),
        )
        allocator.allocate(
            NewClassProposal(
                name_slug="navigation",
                display_name_ru="Навигация",
                display_name_en="",
                description="Описание навигации.",
            ),
            level=1,
            parent_path="task",
            triggered_by_section_id="sec_x",
        )
        # После allocate seed-entry должен получить embedding в registry.
        updated = reg.get_by_bit(level=1, parent_path="task", bit_index=0)
        assert updated.embedding == [1.0, 0.0, 0.0]
