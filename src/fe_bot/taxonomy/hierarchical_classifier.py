"""HierarchicalClassifier (SETUP-12 / T-S12-040).

Оркестратор иерархической классификации одной секции:

    L0 → (apply bits, pick primary) → L1 → ... → L2 → ClassificationState

Логика:
1. На каждом уровне k:
   a. Берёт кандидаты из ``TaxonomyRegistry.list_active_under(level=k, parent_path=...)``.
   b. Вызывает ``LLMClassifier.classify(level=k, ...)`` → ``Decision``.
   c. Если ``Decision.UNKNOWN`` → cascading-stop, выставляет
      ``unknown_at_level = k``, останавливается.
   d. Если ``Decision.NEW`` → ``AutoAllocator.allocate(proposal, ...)`` →
      ``AllocationResult``. Бит, на который указывает allocation,
      выставляется в bitmap; ``AutoCreationRecord`` накапливается.
   e. Если ``Decision.EXISTING`` → для каждого ``ExistingSelection`` с
      ``confidence >= T_SET`` бит выставляется.
   f. Если в итоге ни один бит уровня не выставлен → unknown_at_level = k.
2. После заполнения уровня k выбирается ``primary_l_k_idx`` —
   argmax по ``confidence_per_bit``.
3. Параметры из ``AutoAllocatorConfig``: ``max_depth`` (стартовое 3),
   ``t_set`` (порог установки бита), ``classes_per_level``.

Возвращает ``HierarchicalClassifierResult`` с готовым
``ClassificationState`` + аудитом (`decisions`, `allocations`).

Не записывает ``ClassificationState`` куда-либо — это работа
parser-orchestrator'а (T-S12-041).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from schemas.taxonomy.decision import Decision, DecisionKind
from schemas.taxonomy.state import (
    BITS_PER_LEVEL,
    ClassificationState,
    bit_offset,
)

from fe_bot.taxonomy.auto_allocator import (
    AllocationResult,
    AutoAllocator,
)
from fe_bot.taxonomy.config import AutoAllocatorConfig
from fe_bot.taxonomy.llm_classifier import LLMClassifier
from fe_bot.taxonomy.registry import TaxonomyRegistry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HierarchicalClassifierResult:
    """Результат classify() + audit-полезности.

    ``state`` — итоговый ClassificationState (можно сохранять на ParsedSection).
    ``decisions`` — Decision'ы по каждому опрошенному уровню (0..3 items).
    ``allocations`` — AllocationResult от auto-allocator'а (только если на
    уровне был Decision.NEW). Пусто, если новых классов не создавалось.
    """

    state: ClassificationState
    decisions: list[Decision] = field(default_factory=list)
    allocations: list[AllocationResult] = field(default_factory=list)


class HierarchicalClassifier:
    """Stateless orchestrator. Зависимости — registry + classifier + allocator."""

    def __init__(
        self,
        *,
        registry: TaxonomyRegistry,
        llm_classifier: LLMClassifier,
        auto_allocator: AutoAllocator,
        config: AutoAllocatorConfig | None = None,
    ) -> None:
        self._registry = registry
        self._llm = llm_classifier
        self._allocator = auto_allocator
        self._config = config or AutoAllocatorConfig()

    def classify(
        self,
        *,
        section_id: str,
        section_text: str,
    ) -> HierarchicalClassifierResult:
        """Прогоняет L0 → L1 → L2 с cascading-stop."""
        if not section_text or not section_text.strip():
            raise ValueError("section_text must be non-empty")
        if not section_id:
            raise ValueError("section_id must be non-empty")

        version_id = self._registry.get_active_version_id()
        state = ClassificationState(taxonomy_version_id=version_id)
        result = HierarchicalClassifierResult(state=state)

        # --- Level 0 ---
        l0_outcome = self._run_level(
            level=0,
            parent_path="",
            section_id=section_id,
            section_text=section_text,
            version_id=version_id,
            state=state,
            result=result,
        )
        if l0_outcome is _LevelOutcome.UNKNOWN:
            return self._finalize_unknown(state, result, level=0)

        # primary_l0
        primary_l0_idx = self._argmax_confidence(state, level=0)
        if primary_l0_idx is None:
            return self._finalize_unknown(state, result, level=0)
        state.primary_l0_idx = primary_l0_idx

        primary_l0_entry = self._registry.get_by_bit(
            version_id=version_id,
            level=0,
            parent_path="",
            bit_index=primary_l0_idx,
        )
        primary_l0_slug = primary_l0_entry.class_slug

        also_applies_l0 = self._other_slugs_at_level_0(state, version_id)

        if self._config.max_depth < 2:
            # Если max_depth=1, drill в L1 не идём (для тестов / edge).
            return _replace_state(result, state)

        # --- Level 1 ---
        l1_outcome = self._run_level(
            level=1,
            parent_path=primary_l0_slug,
            section_id=section_id,
            section_text=section_text,
            version_id=version_id,
            state=state,
            result=result,
            primary_l0_slug=primary_l0_slug,
            primary_l0_display_ru=primary_l0_entry.display_name_ru,
            also_applies_l0=also_applies_l0,
        )
        if l1_outcome is _LevelOutcome.UNKNOWN:
            return self._finalize_unknown(state, result, level=1)

        primary_l1_idx = self._argmax_confidence(state, level=1)
        if primary_l1_idx is None:
            return self._finalize_unknown(state, result, level=1)
        state.primary_l1_idx = primary_l1_idx
        primary_l1_entry = self._registry.get_by_bit(
            version_id=version_id,
            level=1,
            parent_path=primary_l0_slug,
            bit_index=primary_l1_idx,
        )
        primary_l1_slug = primary_l1_entry.class_slug

        if self._config.max_depth < 3:
            return _replace_state(result, state)

        # --- Level 2 ---
        l2_parent_path = f"{primary_l0_slug}.{primary_l1_slug}"
        l2_outcome = self._run_level(
            level=2,
            parent_path=l2_parent_path,
            section_id=section_id,
            section_text=section_text,
            version_id=version_id,
            state=state,
            result=result,
            primary_l0_slug=primary_l0_slug,
            primary_l0_display_ru=primary_l0_entry.display_name_ru,
            primary_l1_slug=primary_l1_slug,
            primary_l1_display_ru=primary_l1_entry.display_name_ru,
            also_applies_l0=also_applies_l0,
        )
        if l2_outcome is _LevelOutcome.UNKNOWN:
            return self._finalize_unknown(state, result, level=2)

        return _replace_state(result, state)

    # ------------------------------------------------------------------
    # Single-level execution
    # ------------------------------------------------------------------

    def _run_level(
        self,
        *,
        level: int,
        parent_path: str,
        section_id: str,
        section_text: str,
        version_id: str,
        state: ClassificationState,
        result: HierarchicalClassifierResult,
        primary_l0_slug: str | None = None,
        primary_l0_display_ru: str | None = None,
        primary_l1_slug: str | None = None,
        primary_l1_display_ru: str | None = None,
        also_applies_l0: list[str] | None = None,
    ) -> _LevelOutcome:
        """Один уровень: LLM → apply bits. Возвращает CONTINUE или UNKNOWN."""
        candidates = self._registry.list_active_under(
            version_id=version_id,
            level=level,
            parent_path=parent_path,
        )
        free = self._registry.free_slots(
            version_id=version_id,
            level=level,
            parent_path=parent_path,
        )
        decision = self._llm.classify(
            level=level,
            parent_path=parent_path,
            candidates=candidates,
            section_text=section_text,
            free_slots_count=len(free),
            primary_l0_slug=primary_l0_slug,
            primary_l0_display_ru=primary_l0_display_ru,
            primary_l1_slug=primary_l1_slug,
            primary_l1_display_ru=primary_l1_display_ru,
            also_applies_l0=also_applies_l0,
        )
        result.decisions.append(decision)
        self._update_overall_confidence(state, level, decision.overall_confidence)

        if decision.kind == DecisionKind.UNKNOWN:
            logger.info(
                "HierarchicalClassifier: UNKNOWN at level=%d (section=%s): %s",
                level,
                section_id,
                decision.reason[:120],
            )
            return _LevelOutcome.UNKNOWN

        bits_set_at_level = self._apply_decision(
            state=state,
            result=result,
            decision=decision,
            level=level,
            parent_path=parent_path,
            section_id=section_id,
            version_id=version_id,
        )

        if not bits_set_at_level:
            logger.info(
                "HierarchicalClassifier: no bits set at level=%d after "
                "decision=%s (section=%s, all confidences below T_SET=%.2f)",
                level,
                decision.kind.value,
                section_id,
                self._config.t_set,
            )
            return _LevelOutcome.UNKNOWN

        return _LevelOutcome.CONTINUE

    def _apply_decision(
        self,
        *,
        state: ClassificationState,
        result: HierarchicalClassifierResult,
        decision: Decision,
        level: int,
        parent_path: str,
        section_id: str,
        version_id: str,
    ) -> bool:
        """Применяет Decision к state. Возвращает True если был выставлен
        хотя бы один бит."""
        any_bit_set = False
        if decision.kind == DecisionKind.EXISTING:
            for sel in decision.selected:
                self._record_bit_confidence(state, level, sel.bit, sel.confidence)
                if sel.confidence >= self._config.t_set:
                    self._set_bit(state, level, sel.bit)
                    self._registry.increment_usage(
                        version_id=version_id,
                        level=level,
                        parent_path=parent_path,
                        bit_index=sel.bit,
                    )
                    any_bit_set = True
        elif decision.kind == DecisionKind.NEW:
            # proposal валидирован Decision-инвариантом; allocator решит,
            # reuse-existing или auto-create.
            assert decision.proposal is not None
            allocation = self._allocator.allocate(
                decision.proposal,
                level=level,
                parent_path=parent_path,
                triggered_by_section_id=section_id,
                version_id=version_id,
            )
            result.allocations.append(allocation)
            # Confidence для NEW берём из overall (allocator confidence не
            # имеет — это сила attribution, а не «насколько применимо»).
            bit_conf = decision.overall_confidence
            self._record_bit_confidence(
                state, level, allocation.bit_index, bit_conf
            )
            if bit_conf >= self._config.t_set:
                self._set_bit(state, level, allocation.bit_index)
                self._registry.increment_usage(
                    version_id=version_id,
                    level=level,
                    parent_path=parent_path,
                    bit_index=allocation.bit_index,
                )
                any_bit_set = True
                if allocation.auto_creation_record is not None:
                    state.auto_created_bits.append(
                        allocation.auto_creation_record
                    )
        return any_bit_set

    # ------------------------------------------------------------------
    # State mutation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_bit(state: ClassificationState, level: int, bit_in_level: int) -> None:
        mask = 1 << bit_offset(level, bit_in_level)
        state.classification_bitmap |= mask

    @staticmethod
    def _record_bit_confidence(
        state: ClassificationState,
        level: int,
        bit_in_level: int,
        confidence: float,
    ) -> None:
        key = f"{level}:{bit_in_level}"
        state.confidence_per_bit[key] = float(confidence)

    @staticmethod
    def _update_overall_confidence(
        state: ClassificationState, level: int, value: float
    ) -> None:
        # confidence_per_level — tuple (immutable). Заменяем целиком.
        cl = list(state.confidence_per_level)
        cl[level] = float(value)
        state.confidence_per_level = (cl[0], cl[1], cl[2])

    @staticmethod
    def _argmax_confidence(
        state: ClassificationState, level: int
    ) -> int | None:
        """Возвращает bit_in_level с максимальным confidence_per_bit среди
        реально выставленных бит. None если бит на уровне нет."""
        bits = state.bits_at(level)
        if not bits:
            return None
        best_bit = bits[0]
        best_conf = state.confidence_per_bit.get(f"{level}:{best_bit}", 0.0)
        for b in bits[1:]:
            conf = state.confidence_per_bit.get(f"{level}:{b}", 0.0)
            if conf > best_conf:
                best_bit = b
                best_conf = conf
        return best_bit

    def _other_slugs_at_level_0(
        self, state: ClassificationState, version_id: str
    ) -> list[str]:
        """Список slug'ов выставленных L0-бит, исключая primary."""
        bits = state.bits_at(0)
        out: list[str] = []
        for b in bits:
            if b == state.primary_l0_idx:
                continue
            entry = self._registry.get_by_bit(
                version_id=version_id,
                level=0,
                parent_path="",
                bit_index=b,
            )
            out.append(entry.class_slug)
        return out

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------

    def _finalize_unknown(
        self,
        state: ClassificationState,
        result: HierarchicalClassifierResult,
        *,
        level: int,
    ) -> HierarchicalClassifierResult:
        """Помечает state.unknown_at_level и обнуляет биты уровней >= k."""
        # Обнулить биты уровней >= level (для cascading-инварианта схемы).
        for lvl in range(level, 3):
            mask = _level_mask(lvl)
            state.classification_bitmap &= ~mask & 0x3FFFFFFF
            # primary этих уровней тоже сбросить
            if lvl == 0:
                state.primary_l0_idx = None
            if lvl == 1:
                state.primary_l1_idx = None
        # confidence_per_bit чистить от записей этих уровней
        prefix_remove = {f"{lvl}:" for lvl in range(level, 3)}
        keep = {
            k: v
            for k, v in state.confidence_per_bit.items()
            if not any(k.startswith(p) for p in prefix_remove)
        }
        state.confidence_per_bit.clear()
        state.confidence_per_bit.update(keep)
        state.unknown_at_level = level
        return _replace_state(result, state)


class _LevelOutcome:
    """Маркеры для control-flow между уровнями."""

    CONTINUE = "continue"
    UNKNOWN = "unknown"


def _level_mask(level: int) -> int:
    return ((1 << BITS_PER_LEVEL) - 1) << (level * BITS_PER_LEVEL)


def _replace_state(
    result: HierarchicalClassifierResult,
    state: ClassificationState,
) -> HierarchicalClassifierResult:
    """Поскольку state — mutable Pydantic-модель, просто проверяем, что
    итоговый объект всё ещё валиден (бросит ValidationError если нет).
    """
    # Прогон через model_validate ловит нарушения инвариантов после
    # in-place мутаций.
    revalidated = ClassificationState.model_validate(state.model_dump())
    return HierarchicalClassifierResult(
        state=revalidated,
        decisions=result.decisions,
        allocations=result.allocations,
    )
