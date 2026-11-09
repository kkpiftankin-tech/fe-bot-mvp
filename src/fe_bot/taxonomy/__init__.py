"""Taxonomy module (SETUP-12).

Иерархическая LLM-классификация секций. См.
docs/02-system/features/SETUP-12-llm-taxonomy-classification.md.

S1 (current): registry + repositories + seed loader + embedding index.
S2+ (next): auto-allocator, LLM classifier, hierarchical orchestrator.
"""

from fe_bot.taxonomy.agent_focus import (
    TaxonomyFocus,
    TaxonomyPathPattern,
    collect_focuses,
)
from fe_bot.taxonomy.audit import TaxonomyAuditEmitter
from fe_bot.taxonomy.auto_allocator import (
    AllocationResult,
    AllocationSource,
    AutoAllocator,
)
from fe_bot.taxonomy.bridge_sync import (
    InMemorySectionClassTagsRepository,
    SectionClassTag,
    SectionClassTagsBridge,
    SectionClassTagsRepository,
)
from fe_bot.taxonomy.card_metadata import (
    build_taxonomy_front_matter,
    build_taxonomy_section_dict,
)
from fe_bot.taxonomy.config import (
    AutoAllocatorConfig,
    TaxonomyConfigError,
    default_config_path,
)
from fe_bot.taxonomy.doc_type_detector import TaxonomyDocTypeDetector
from fe_bot.taxonomy.embedding_index import (
    EmbeddingComputer,
    EmbeddingIndex,
)
from fe_bot.taxonomy.entry_repository import (
    DuplicateRegistryEntryError,
    InMemoryTaxonomyEntryRepository,
    RegistryEntryNotFoundError,
    TaxonomyEntryRepository,
)
from fe_bot.taxonomy.exceptions import (
    NoActiveTaxonomyVersionError,
    TaxonomyError,
)
from fe_bot.taxonomy.hierarchical_classifier import (
    HierarchicalClassifier,
    HierarchicalClassifierResult,
)
from fe_bot.taxonomy.llm_classifier import (
    LLMClassifier,
    LLMClassifierError,
)
from fe_bot.taxonomy.llm_gateway_embedder import LLMGatewayEmbeddingComputer
from fe_bot.taxonomy.metrics import TaxonomyMetrics
from fe_bot.taxonomy.prompt_renderer import (
    ClassificationPromptInput,
    ClassificationPromptRenderer,
    PromptTemplateNotFoundError,
)
from fe_bot.taxonomy.registry import TaxonomyRegistry
from fe_bot.taxonomy.retrieval import (
    BitTest,
    TaxonomyFilter,
    apply_filter_to_hits,
    build_payload,
)
from fe_bot.taxonomy.section_classifier_adapter import (
    HierarchicalSectionClassifier,
    SectionClassifierProtocol,
)
from fe_bot.taxonomy.seed_loader import (
    SeedFormatError,
    load_seed_taxonomy,
)
from fe_bot.taxonomy.version_repository import (
    DuplicateTaxonomyVersionError,
    InMemoryTaxonomyVersionRepository,
    TaxonomyVersionNotFoundError,
    TaxonomyVersionRepository,
)

__all__ = [
    "AllocationResult",
    "AllocationSource",
    "AutoAllocator",
    "AutoAllocatorConfig",
    "BitTest",
    "ClassificationPromptInput",
    "ClassificationPromptRenderer",
    "DuplicateRegistryEntryError",
    "DuplicateTaxonomyVersionError",
    "EmbeddingComputer",
    "EmbeddingIndex",
    "HierarchicalClassifier",
    "HierarchicalClassifierResult",
    "HierarchicalSectionClassifier",
    "InMemorySectionClassTagsRepository",
    "InMemoryTaxonomyEntryRepository",
    "InMemoryTaxonomyVersionRepository",
    "LLMClassifier",
    "LLMClassifierError",
    "LLMGatewayEmbeddingComputer",
    "NoActiveTaxonomyVersionError",
    "PromptTemplateNotFoundError",
    "RegistryEntryNotFoundError",
    "SectionClassTag",
    "SectionClassTagsBridge",
    "SectionClassTagsRepository",
    "SectionClassifierProtocol",
    "SeedFormatError",
    "TaxonomyAuditEmitter",
    "TaxonomyConfigError",
    "TaxonomyDocTypeDetector",
    "TaxonomyEntryRepository",
    "TaxonomyFilter",
    "TaxonomyFocus",
    "TaxonomyMetrics",
    "TaxonomyPathPattern",
    "TaxonomyError",
    "TaxonomyRegistry",
    "TaxonomyVersionNotFoundError",
    "TaxonomyVersionRepository",
    "apply_filter_to_hits",
    "build_payload",
    "build_taxonomy_front_matter",
    "build_taxonomy_section_dict",
    "collect_focuses",
    "default_config_path",
    "load_seed_taxonomy",
]
