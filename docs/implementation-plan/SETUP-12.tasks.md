# SETUP-12 — Implementation plan

Реализация SETUP-12 «Hierarchical LLM Taxonomy Classification» по
слайсам S0..S10. Основной источник требований:
[docs/02-system/features/SETUP-12-llm-taxonomy-classification.md](../02-system/features/SETUP-12-llm-taxonomy-classification.md).

## Контекст и зависимости

- **Вход:** SETUP-04 завершён. Существует `DocumentParserOrchestrator`
  + rule-based `SectionClassifier`. ParsedSection несёт плоский
  `SectionType` enum.
- **Выход:** ParsedSection несёт `ClassificationState` (bitmap + primary
  indices). RAGCard, retrieval и runtime используют hierarchical
  metadata. Старый enum депрекейтится через derive-property.
- **Существующий MVP-каркас:** ничего не существует; всё в `src/fe_bot/taxonomy/` — новое.
- **Зависимости от других SETUP'ов:**
  - SETUP-05 (RAG Card Generation) — переписывает `DocTypeDetector`
    и `PromptTemplateRegistry` на hierarchy.
  - SETUP-08/09 (chunking/indexing) — добавляет taxonomy fields в payload.
  - SETUP-10 (retrieval) — bitwise filters.
- **Внешние зависимости:** LLMGateway, EmbeddingGateway (для
  similarity-gate).

## Метрики плана

- **10 слайсов** (S0..S10).
- **~50 задач** (T-S12-001..050), детализированы ниже.
- **~250 новых тестов** (unit + component + integration).
- **Несколько commit'ов на слайс** (atomicity по нодам/сервисам).

---

## Slice 0 — Foundation (этот PR-pack)

### T-S12-001 — Schemas

Target files:
- `schemas/taxonomy/__init__.py`
- `schemas/taxonomy/decision.py`
- `schemas/taxonomy/registry.py`
- `schemas/taxonomy/state.py`

Acceptance:
- Pydantic-валидация для всех контрактов.
- Bit-маски и `bit_offset()` соответствуют ADR-HTC-02.
- Cascading-unknown инвариант проверен в model_validator'е.
- Тест: `tests/unit/schemas/test_taxonomy_*.py` (зелёный).

### T-S12-002 — Config + seed

Target files:
- `config/taxonomy/auto_allocation.yaml`
- `seed/taxonomy/v1_0_0.yaml`

Acceptance:
- Парсится в Pydantic-настройки (loader будет в S1).
- Все 9 seed-L0 классов имеют `doc_type_hint`.
- Bit 9 на L0 свободен под auto-create.

### T-S12-003 — Prompt template

Target: `prompts/classification/classify_at_level.txt`.

Acceptance:
- Jinja-условные на context-блоки (L0 → L1 → L2).
- Test rendering с 3 разными level'ами (через `jinja2.Template.render`).
- Документирован в [LLM-CLS-01](../07-contracts/LLM-CLS-01-classify-at-level.md).

### T-S12-004 — Docs

Target files:
- `docs/02-system/features/SETUP-12-llm-taxonomy-classification.md`
- `docs/03-architecture/adr/ADR-HTC-01..08.md` (8 файлов)
- `docs/04-domain/taxonomy.md`
- `docs/06-rag/taxonomy.md`
- `docs/00-methodology/taxonomy-governance.md`
- `docs/05-agents/taxonomy-classifier-agent.md`
- `docs/07-contracts/LLM-CLS-01-classify-at-level.md`
- `docs/09-langgraph/ClassifySectionSubgraph.md`
- `docs/tech-debt/TD-HTC-001..003.md`

Acceptance: все ссылки между файлами разрешаются; формат соответствует существующим в репо.

---

## Slice 1 — Taxonomy Registry service (без LLM)

### T-S12-010 — Registry skeleton

Target: `src/fe_bot/taxonomy/registry.py`.

API:
```python
class TaxonomyRegistry:
    def __init__(self, version_repo, entry_repo) -> None: ...
    def get_active_version(self) -> TaxonomyVersion: ...
    def list_active(
        self, version_id: str, level: int, parent_path: str,
    ) -> list[TaxonomyBitRegistryEntry]: ...
    def get_by_bit(
        self, version_id: str, level: int, parent_path: str, bit: int,
    ) -> TaxonomyBitRegistryEntry | None: ...
    def free_slots(
        self, version_id: str, level: int, parent_path: str,
    ) -> list[int]: ...  # 0..9, return сорт. список свободных
    def bump_version_patch(self) -> str: ...  # returns new version_id
```

Acceptance: unit-тесты `tests/unit/taxonomy/test_registry.py`.

### T-S12-011 — Repositories (in-memory MVP)

Target: `src/fe_bot/taxonomy/version_repository.py`,
`entry_repository.py`.

Acceptance: Protocol-based, тривиальный in-memory dict-based
backend; интерфейс готов для PG-замены.

### T-S12-012 — Seed loader

Target: `src/fe_bot/taxonomy/seed_loader.py`.

Acceptance: загружает `seed/taxonomy/v1_0_0.yaml` в активный
`TaxonomyVersion`. Embedding для seed-классов вычисляется
lazy при первом запросе (см. T-S12-013).

### T-S12-013 — Embedding integration

Target: `src/fe_bot/taxonomy/embedding_index.py`.

Acceptance:
- `compute_embedding(name + " " + description)` через существующий
  `EmbeddingGateway`.
- LRU-кэш по `hash(text)`.
- `cosine_similarity(a, b)` utility.

---

## Slice 2 — Auto-allocator

### T-S12-020 — AutoAllocator core

Target: `src/fe_bot/taxonomy/auto_allocator.py`.

API:
```python
class AutoAllocator:
    def allocate(
        self, proposal: NewClassProposal,
        level: int, parent_path: str,
        triggered_by_section_id: str,
    ) -> AllocationResult:
        # returns: bit_index + AutoCreationRecord OR reuse existing
```

Acceptance:
- Similarity-gate с порогами из config'а.
- Free-slot allocation с advisory-lock.
- Force-merge при overflow.
- Logging событий + metrics.

### T-S12-021 — Concurrency tests

Target: `tests/component/taxonomy/test_auto_allocator_concurrent.py`.

Acceptance: симуляция 5 параллельных NEW под одним parent_path
с похожими предложениями → создаётся 1 класс, остальные reuse.

---

## Slice 3 — LLMClassifier (single level)

### T-S12-030 — Prompt rendering

Target: `src/fe_bot/taxonomy/prompt_renderer.py`.

Acceptance: рендеринг template'а с PromptContext; snapshot-тесты.

### T-S12-031 — LLMClassifier

Target: `src/fe_bot/taxonomy/llm_classifier.py`.

API:
```python
class LLMClassifier:
    def classify(
        self, section: ParsedSection, *,
        level: int, parent_path: str,
        candidates: list[TaxonomyBitRegistryEntry],
        primary_l0_slug: str | None = None,
        primary_l1_slug: str | None = None,
    ) -> Decision
```

Acceptance:
- LLMGateway.generate_structured с `Decision` schema.
- Lenient normalization (см. подход в [llm_adapter.py](../../src/fe_bot/setup/rag_card_generation/llm_adapter.py)).
- Tests: `FakeGateway` returns 3-way scenarios.

---

## Slice 4 — Hierarchical orchestrator + integration

### T-S12-040 — HierarchicalClassifier

Target: `src/fe_bot/taxonomy/hierarchical_classifier.py`.

API:
```python
class HierarchicalClassifier:
    def classify(self, section: ParsedSection) -> ClassificationState
```

Acceptance: 3 уровня sequentially; cascading-unknown working.

### T-S12-041 — Parser orchestrator swap

Target: `src/fe_bot/setup/parser/orchestrator.py`.

Acceptance:
- Feature flag `taxonomy_mode` ∈ `{rule_based, llm}`.
- При `llm` — `HierarchicalClassifier` заменяет
  `SectionClassifier.apply_to_sections`.
- ParsedSection получает `classification_state`.
- Старое поле `section_type` derive'ится из primary_l0_slug.

### T-S12-042 — Bridge table writer

Target: `src/fe_bot/taxonomy/bridge_sync.py`.

Acceptance: при сохранении ParsedSection синхронизирует
`section_class_tags`.

---

## Slice 5 — RAG card generation propagation

### T-S12-050 — DocTypeDetector swap

Target: `src/fe_bot/setup/rag_card_generation/doc_type_detector.py`.

Acceptance:
- Читает `classification_state.primary_l0_idx` → `doc_type_hint`
  из registry.
- Старая `_DIRECT_MAPPING` уходит.

### T-S12-051 — PromptTemplateRegistry hierarchical lookup

Target: `src/fe_bot/setup/rag_card_generation/prompt_template_registry.py`.

Acceptance:
- Lookup по `taxonomy_path` с fallback вверх по дереву.
- Fallback на `default` если ничего не найдено.

### T-S12-052 — RAG card metadata extension

Target: `schemas/rag/*` и `src/fe_bot/setup/rag_card_generation/orchestrator.py`.

Acceptance:
- `front_matter.taxonomy_path`, `taxonomy_node_id`,
  `taxonomy_version_id`, `classification_bitmap` обязательны.

### T-S12-053 — ConfidenceCalculator penalty

Target: `src/fe_bot/setup/rag_card_generation/confidence_calculator.py`.

Acceptance:
- Добавлен penalty `parser_unknown_at_level` (текущий разрыв между
  parser-confidence и card-confidence закрыт).

---

## Slice 6 — Retrieval / Runtime propagation

### T-S12-060 — Vector index payload

Target: `src/fe_bot/vector_index/service.py`.

Acceptance: payload содержит `bitmap_l0`, `bitmap_l1`, `bitmap_l2`,
`primary_l0`, `primary_l1`, `taxonomy_path`, `taxonomy_version`.

### T-S12-061 — RetrievalService bitwise filters

Target: `src/fe_bot/retrieval/service.py`.

Acceptance:
- API принимает `taxonomy_filter: TaxonomyFilter`.
- Builder для bitwise expression'ов и bridge-таблицы lookup'ов.

### T-S12-062 — Runtime agents taxonomy_focus

Target: `src/fe_bot/agents/*` (рантайм-агенты).

Acceptance:
- Каждый агент объявляет `taxonomy_focus: list[str]`
  (wildcards разрешены: `"task.*"`).
- RetrievalService применяет фильтр автоматически.

---

## Slice 7 — Frontend (TaxonomyTreeView, deferred to admin UI)

### T-S12-070 — TaxonomyTreeView component

Target: `frontend/src/components/Taxonomy/TreeView.tsx`.

Acceptance: рендерит дерево активной version с usage_count.

### T-S12-071 — Section classification badge

Target: `frontend/src/components/Wizard/sections/ClassificationBadge.tsx`.

Acceptance: показывает `taxonomy_path` секции + confidence per level.

### T-S12-072 — Step «Classification overview» в wizard'е

Target: новый step после parsing.

Acceptance:
- Полная картина классификации всех секций job'а.
- Drill-down по узлам.

---

## Slice 8 — Migration

### T-S12-080 — Backfill existing sections

Target: `src/fe_bot/taxonomy/migration/v0_to_v1.py`.

Acceptance:
- CLI: `python -m fe_bot.taxonomy.migration v0_to_v1 --setup-job <id>`.
- Все ParsedSection получают
  `classification_state = ClassificationState(
      classification_bitmap=1<<bit_of_legacy_section_type,
      primary_l0_idx=bit_of_legacy_section_type, ...,
      classification_method="seeded_migration"
  )`.
- Идемпотентность; миграция логирует в `migration_log` таблицу.

### T-S12-081 — RAG card backfill

Target: `src/fe_bot/taxonomy/migration/rag_card_backfill.py`.

Acceptance: существующие карточки получают `taxonomy_*` поля в
front_matter; bitmap наследуется от родительской секции.

---

## Slice 9 — Cleanup

### T-S12-090 — Remove rule-based SectionClassifier (feature-flagged)

Target: `src/fe_bot/setup/parser/classifier.py`.

Acceptance: помечен `@deprecated`; вызывается только при
`taxonomy_mode=rule_based`. Default `llm`.

### T-S12-091 — Drop markdown_parser._SECTION_TYPE_KEYWORDS

Target: `src/fe_bot/setup/parser/markdown_parser.py`.

Acceptance: `_detect_section_type` всегда возвращает
`SectionType.OTHER` (HTC сделает реальную работу).

---

## Slice 10 — Analytics & metrics

### T-S12-100 — Metrics registry

Target: `src/fe_bot/observability/metrics.py`.

Acceptance: метрики из TD-HTC-003 (`taxonomy_classification_total`,
`taxonomy_force_merge_total`, `taxonomy_slots_used` и др.).

### T-S12-101 — Grafana dashboard

Target: `docs/observability/dashboards/taxonomy-health.json`.

Acceptance: панель + alert-правила.

### T-S12-102 — Audit logging

Target: `src/fe_bot/audit/taxonomy_events.py`.

Acceptance: все AutoCreationRecord и force-merge события
отправляются в AuditService.

---

## Test plan / coverage цели

- **Unit (schemas):** ≥95% покрытие `schemas/taxonomy/*`.
- **Unit (taxonomy services):** ≥85% покрытие `src/fe_bot/taxonomy/*`.
- **Component:** все Decision-сценарии для `LLMClassifier` (9
  ситуаций: 3 × 3 = EXISTING × {valid, low-conf, multi-bit} плюс NEW
  × {free, reuse, overflow} плюс UNKNOWN × {at L0, at L1, at L2}).
- **Integration:** parser → classifier → save; orchestrator → RAG card.
- **E2E:** один полный wizard-проход на goldens после S5.

## Acceptance суммарный

После всех 10 слайсов:
- Default `taxonomy_mode = llm`.
- Удалены/задеприкейчены: rule-based classifier, markdown_parser
  keywords, `_DIRECT_MAPPING` в DocTypeDetector.
- На golden setup_job'е:
  - 90%+ секций классифицируются на L0.
  - 70%+ секций — на L1.
  - 50%+ секций — на L2.
- Retrieval-фильтры работают по `taxonomy_focus`.

## Открытые задачи (для дальнейших sprint'ов)

- TD-HTC-001 — re-classification после version bump.
- TD-HTC-002 — admin UI таксономии.
- TD-HTC-003 — drift alerts.
