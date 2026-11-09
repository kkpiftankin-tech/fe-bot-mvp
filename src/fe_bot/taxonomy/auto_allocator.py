"""AutoAllocator (SETUP-12 / T-S12-020).

Материализует LLM-предложение нового класса (``NewClassProposal``) в
bit-registry. Логика:

1. Idempotency check — если class_slug уже существует под parent_path,
   reuse existing.
2. Similarity gate — если предложение очень похоже на существующий
   класс (cosine ≥ SIM_REUSE), reuse.
3. Free slot — если под parent_path есть свободный бит, allocate
   новый.
4. Overflow — если свободных битов нет, force-merge с ближайшим
   (см. ADR-HTC-08).

Concurrency: per-(version, level, parent_path) advisory-lock через
``TaxonomyRegistry.acquire_allocation_lock`` исключает race condition'ы
при параллельных NEW-предложениях.

Идемпотентен по class_slug: повторный вызов с тем же proposal под
тем же parent_path даёт SLUG_MATCH без побочных эффектов.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from schemas.taxonomy.decision import NewClassProposal
from schemas.taxonomy.registry import TaxonomyBitRegistryEntry
from schemas.taxonomy.state import AutoCreationRecord

from fe_bot.taxonomy.config import AutoAllocatorConfig
from fe_bot.taxonomy.embedding_index import (
    EmbeddingIndex,
    cosine_similarity,
)
from fe_bot.taxonomy.registry import TaxonomyRegistry

logger = logging.getLogger(__name__)


class AllocationSource(StrEnum):
    """Откуда взялся итоговый bit для allocation."""

    SLUG_MATCH = "slug_match"
    SIMILARITY_REUSE = "similarity_reuse"
    AUTO_CREATE = "auto_create"
    FORCE_MERGE = "force_merge"
    CLASS_OVERFLOW = "class_overflow"


@dataclass(slots=True, frozen=True)
class AllocationResult:
    """Итог одного вызова ``AutoAllocator.allocate``.

    ``target_entry`` — это registry-запись, на которую теперь указывает
    bit (либо существующая, либо только что созданная).

    ``auto_creation_record`` непустой только для source == AUTO_CREATE.

    ``warning_message`` непустой для FORCE_MERGE и CLASS_OVERFLOW.
    """

    bit_index: int
    source: AllocationSource
    target_entry: TaxonomyBitRegistryEntry
    similarity_to_closest: float | None
    closest_existing_slug: str | None
    auto_creation_record: AutoCreationRecord | None
    warning_message: str | None


class AutoAllocator:
    """Stateless allocator поверх ``TaxonomyRegistry`` + ``EmbeddingIndex``."""

    def __init__(
        self,
        *,
        registry: TaxonomyRegistry,
        embedding_index: EmbeddingIndex,
        config: AutoAllocatorConfig | None = None,
    ) -> None:
        self._registry = registry
        self._embeddings = embedding_index
        self._config = config or AutoAllocatorConfig()

    @property
    def config(self) -> AutoAllocatorConfig:
        return self._config

    def allocate(
        self,
        proposal: NewClassProposal,
        *,
        level: int,
        parent_path: str,
        triggered_by_section_id: str,
        version_id: str | None = None,
    ) -> AllocationResult:
        """Материализует proposal в bit-registry. См. модульный docstring.

        Под advisory-lock'ом (version_id, level, parent_path).
        """
        vid = version_id or self._registry.get_active_version_id()
        with self._registry.acquire_allocation_lock(
            version_id=vid, level=level, parent_path=parent_path
        ):
            # 1. Slug idempotency
            existing_by_slug = self._registry.find_by_slug(
                version_id=vid,
                level=level,
                parent_path=parent_path,
                class_slug=proposal.name_slug,
            )
            if existing_by_slug is not None:
                logger.debug(
                    "AutoAllocator: slug match for %r at %s/%d → bit %d",
                    proposal.name_slug,
                    parent_path,
                    level,
                    existing_by_slug.bit_index,
                )
                return AllocationResult(
                    bit_index=existing_by_slug.bit_index,
                    source=AllocationSource.SLUG_MATCH,
                    target_entry=existing_by_slug,
                    similarity_to_closest=None,
                    closest_existing_slug=None,
                    auto_creation_record=None,
                    warning_message=None,
                )

            # 2. Similarity gate
            emb_new = self._embeddings.get_or_compute(
                self._embedding_text(
                    proposal.display_name_ru, proposal.description
                )
            )
            neighbors = self._registry.list_active_under(
                version_id=vid, level=level, parent_path=parent_path
            )
            similarities = self._compute_similarities(
                emb_new=emb_new,
                neighbors=neighbors,
                version_id=vid,
                level=level,
                parent_path=parent_path,
            )
            similarities.sort(key=lambda t: t[1], reverse=True)
            closest_entry: TaxonomyBitRegistryEntry | None = (
                similarities[0][0] if similarities else None
            )
            closest_sim: float = similarities[0][1] if similarities else 0.0

            if (
                closest_entry is not None
                and closest_sim >= self._config.sim_reuse
            ):
                logger.info(
                    "AutoAllocator: similarity_reuse %s ~ %s (sim=%.3f) at %s/%d",
                    proposal.name_slug,
                    closest_entry.class_slug,
                    closest_sim,
                    parent_path,
                    level,
                )
                return AllocationResult(
                    bit_index=closest_entry.bit_index,
                    source=AllocationSource.SIMILARITY_REUSE,
                    target_entry=closest_entry,
                    similarity_to_closest=closest_sim,
                    closest_existing_slug=closest_entry.class_slug,
                    auto_creation_record=None,
                    warning_message=None,
                )

            # 3. Free slot allocation
            free = self._registry.free_slots(
                version_id=vid, level=level, parent_path=parent_path
            )
            if free:
                new_bit = free[0]
                created_at = datetime.now(tz=UTC)
                new_entry = TaxonomyBitRegistryEntry(
                    version_id=vid,
                    level=level,
                    parent_path=parent_path,
                    bit_index=new_bit,
                    class_slug=proposal.name_slug,
                    display_name_ru=proposal.display_name_ru,
                    display_name_en=proposal.display_name_en,
                    description=proposal.description,
                    auto_created=True,
                    created_at=created_at,
                    created_by_section=triggered_by_section_id,
                    embedding=emb_new,
                )
                self._registry.create_entry(new_entry)
                record = AutoCreationRecord(
                    level=level,
                    parent_path=parent_path,
                    bit_index=new_bit,
                    class_slug=proposal.name_slug,
                    triggered_by_section_id=triggered_by_section_id,
                    created_at=created_at,
                    similarity_to_closest=(
                        closest_sim if closest_entry is not None else None
                    ),
                    closest_existing_slug=(
                        closest_entry.class_slug
                        if closest_entry is not None
                        else None
                    ),
                )
                logger.info(
                    "AutoAllocator: auto_create %s at %s/%d bit=%d (closest_sim=%.3f)",
                    proposal.name_slug,
                    parent_path,
                    level,
                    new_bit,
                    closest_sim,
                )
                return AllocationResult(
                    bit_index=new_bit,
                    source=AllocationSource.AUTO_CREATE,
                    target_entry=new_entry,
                    similarity_to_closest=(
                        closest_sim if closest_entry is not None else None
                    ),
                    closest_existing_slug=(
                        closest_entry.class_slug
                        if closest_entry is not None
                        else None
                    ),
                    auto_creation_record=record,
                    warning_message=None,
                )

            # 4. Overflow
            # Свободных битов нет. closest_entry должен быть задан
            # (10 слотов заняты ⇒ >=1 neighbour).
            assert closest_entry is not None, (
                "AutoAllocator overflow without neighbours: "
                "invariant violation (10 slots occupied implies >=1 entry)"
            )
            if closest_sim >= self._config.sim_force_merge:
                source = AllocationSource.FORCE_MERGE
                warning = (
                    f"force_merge: parent_path={parent_path!r} level={level} "
                    f"full; proposal {proposal.name_slug!r} merged with "
                    f"{closest_entry.class_slug!r} (sim={closest_sim:.3f})"
                )
                logger.warning("AutoAllocator: %s", warning)
            else:
                source = AllocationSource.CLASS_OVERFLOW
                warning = (
                    f"class_overflow: parent_path={parent_path!r} level={level} "
                    f"full; no similar neighbour; proposal {proposal.name_slug!r} "
                    f"force-merged with {closest_entry.class_slug!r} "
                    f"(sim={closest_sim:.3f} < SIM_FORCE_MERGE)"
                )
                logger.warning("AutoAllocator: %s", warning)
            return AllocationResult(
                bit_index=closest_entry.bit_index,
                source=source,
                target_entry=closest_entry,
                similarity_to_closest=closest_sim,
                closest_existing_slug=closest_entry.class_slug,
                auto_creation_record=None,
                warning_message=warning,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _embedding_text(name: str, description: str) -> str:
        return f"{name.strip()} {description.strip()}".strip()

    def _compute_similarities(
        self,
        *,
        emb_new: list[float],
        neighbors: list[TaxonomyBitRegistryEntry],
        version_id: str,
        level: int,
        parent_path: str,
    ) -> list[tuple[TaxonomyBitRegistryEntry, float]]:
        """Считает cosine similarity нового embedding'а с каждым neighbor'ом.

        Если у neighbor'а embedding ещё не вычислен (например, seed-класс) —
        вычисляет lazy через ``EmbeddingIndex`` и обновляет запись в registry
        (для последующих вызовов).
        """
        out: list[tuple[TaxonomyBitRegistryEntry, float]] = []
        for entry in neighbors:
            emb = self._ensure_embedding(
                entry,
                version_id=version_id,
                level=level,
                parent_path=parent_path,
            )
            sim = cosine_similarity(emb_new, emb)
            out.append((entry, sim))
        return out

    def _ensure_embedding(
        self,
        entry: TaxonomyBitRegistryEntry,
        *,
        version_id: str,
        level: int,
        parent_path: str,
    ) -> list[float]:
        if entry.embedding is not None:
            return entry.embedding
        text = self._embedding_text(entry.display_name_ru, entry.description)
        emb = self._embeddings.get_or_compute(text)
        # Lazy materialisation в registry (для persistence + кэш в entry).
        updated = entry.model_copy(update={"embedding": emb})
        try:
            self._registry.update_entry(updated)
        except Exception:  # pragma: no cover - defensive
            # Если update упал по какой-то причине, не падаем целиком —
            # embedding всё равно есть в EmbeddingIndex кэше.
            logger.exception(
                "Failed to persist embedding for %s/%d bit=%d",
                parent_path,
                level,
                entry.bit_index,
            )
        return emb
