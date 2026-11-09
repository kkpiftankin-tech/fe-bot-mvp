"""Taxonomy schemas (SETUP-12).

Contract-first контракты для иерархической LLM-классификации:
- ClassificationState (DTO) — bitmap-состояние + primary indices.
- TaxonomyBitRegistryEntry — описание одного слота в bit-registry.
- TaxonomyVersion — snapshot реестра.
- Decision (ADT) — LLM-решение на одном уровне (EXISTING / NEW / UNKNOWN).
- AutoCreationRecord — аудит-запись для каждого автоматически
  созданного класса.

См. документы:
- docs/02-system/features/SETUP-12-llm-taxonomy-classification.md
- docs/07-contracts/LLM-CLS-01-classify-at-level.md
"""

from schemas.taxonomy.decision import (
    Decision,
    DecisionKind,
    ExistingSelection,
    NewClassProposal,
)
from schemas.taxonomy.registry import (
    TaxonomyBitRegistryEntry,
    TaxonomyBitStatus,
    TaxonomyVersion,
)
from schemas.taxonomy.state import (
    AutoCreationRecord,
    ClassificationState,
)

__all__ = [
    "AutoCreationRecord",
    "ClassificationState",
    "Decision",
    "DecisionKind",
    "ExistingSelection",
    "NewClassProposal",
    "TaxonomyBitRegistryEntry",
    "TaxonomyBitStatus",
    "TaxonomyVersion",
]
