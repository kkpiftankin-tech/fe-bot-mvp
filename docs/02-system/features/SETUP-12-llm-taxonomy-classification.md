# SETUP-12. Иерархическая LLM-классификация секций

## 1. Назначение фичи

**Краткое название:** SETUP-12. Hierarchical LLM Taxonomy Classification (HTC).

**Краткое описание:** Фича заменяет rule-based keyword-классификатор
секций (SETUP-04) на иерархический LLM-классификатор с тремя уровнями
и автоматическим созданием новых классов. Каждая секция получает
30-битный bitmap состояния (10 бит на уровень), позволяющий хранить
multi-class membership и компактно фильтровать в retrieval.

**Какую проблему решает:**

Сегодняшняя классификация в SETUP-04
([classifier.py](../../../src/fe_bot/setup/parser/classifier.py),
[markdown_parser.py](../../../src/fe_bot/setup/parser/markdown_parser.py))
страдает от:

- Закрытого enum'а: всё нераспознанное → `UNKNOWN`, downstream
  отбрасывает.
- Плоской модели: «task ПВО» и «task навигация» неразличимы.
- Двух расходящихся keyword-словарей, второй затирает первый.
- Шумовых ложно-положительных срабатываний на общеупотребительных
  словах.
- Невозможности расширения без code-change.

HTC решает это:

```
section
  → L0 LLM-classify (10 кандидатов глобально)
    → L1 LLM-classify (10 кандидатов под primary_l0)
      → L2 LLM-classify (10 кандидатов под primary_l0.primary_l1)
        → bitmap(30) + primary_l0 + primary_l1
```

При появлении нового семантического паттерна, не покрытого
существующими классами, LLM предлагает новый класс, который
auto-allocator материализует в `taxonomy_bit_registry` без human
review (similarity-gate защищает от дубликатов).

**Для какого бизнес-процесса нужна:** часть Setup-stage, между
SETUP-04 (parsing) и SETUP-05 (RAG card generation). Также влияет
на SETUP-08 (chunking), SETUP-09 (indexing), SETUP-10 (retrieval
tests) и весь Runtime через метаданные карточек.

**Главный пользовательский результат:** секции классифицируются
точно (3 уровня иерархии вместо плоского enum'а), новые домены
автоматически расширяют таксономию, downstream получает богатую
metadata для retrieval и доменно-специализированных runtime-агентов.

---

## 2. Контекст и бизнес-цель

### 2.1. Бизнес-контекст

FE-Bot работает с разнородными доменами (военный, медицинский,
индустриальный, …). Каждый домен имеет свои подкатегории: «task»
в военной системе — это «task ПВО», «task навигация», «task
освещение»; «schema» в банковской — «schema транзакции», «schema
клиент», «schema лимит».

Закрытый enum принципиально не масштабируется без code-change
для каждого нового домена.

### 2.2. Цели

- Восстановить семантическую точность классификации секций (90%+
  правильной классификации на L0, 70%+ на L1 после первых 100
  секций bootstrap-периода).
- Поддержать рост таксономии без code-change.
- Прокачать downstream: точные prompt-templates, точные retrieval-
  фильтры, точные metadata.

### 2.3. Non-goals

- Не создаём admin UI в MVP (отложено в
  [TD-HTC-002](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md)).
- Не реализуем re-classification старых секций
  ([TD-HTC-001](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)).
- Не поддерживаем DAG / poly-hierarchy.
- Не вводим faceted (multi-axis) классификацию.

---

## 3. Принципиальная архитектура

### 3.1. Pipeline классификации

```
ParsedSection
   ↓
[HierarchicalClassifier]
   ↓
   ├── L0: llm_classify(section, parent_path="", candidates=registry.L0)
   │   ├── Decision.EXISTING(bits) → apply_bits + select primary
   │   ├── Decision.NEW(proposal) → similarity_gate → bit | reuse | overflow
   │   └── Decision.UNKNOWN → cascading stop
   │
   ├── L1 (only if L0 определён): llm_classify(..., parent_path=primary_l0_slug)
   │   └── same 3-way decision
   │
   └── L2 (only if L1 определён): llm_classify(..., parent_path="primary_l0.primary_l1")
       └── same 3-way decision
   ↓
ClassificationState(bitmap, primary_l0_idx, primary_l1_idx, unknown_at_level, ...)
   ↓
ParsedSection.classification_state
```

### 3.2. Storage

- `taxonomy_versions` — реестр версий (semver).
- `taxonomy_bit_registry` — каноническая таблица бит-позиций
  каждой версии.
- `section_class_tags` — derived bridge для глобальных
  retrieval-запросов (см. [ADR-HTC-07](../../03-architecture/adr/ADR-HTC-07-bitwise-retrieval-filters.md)).
- `parsed_sections.classification_state` — bitmap-состояние секции.

### 3.3. Контракты

- [schemas/taxonomy/state.py](../../../schemas/taxonomy/state.py) —
  `ClassificationState`, `AutoCreationRecord`.
- [schemas/taxonomy/registry.py](../../../schemas/taxonomy/registry.py) —
  `TaxonomyBitRegistryEntry`, `TaxonomyVersion`.
- [schemas/taxonomy/decision.py](../../../schemas/taxonomy/decision.py) —
  `Decision`, `ExistingSelection`, `NewClassProposal`.

---

## 4. Bitmap-layout

См. [ADR-HTC-02](../../03-architecture/adr/ADR-HTC-02-bitmap-30-layout.md).

```
bit  position : 29 ─── 20 | 19 ─── 10 |  9 ─── 0
                L2 (10)    L1 (10)     L0 (10)
```

- L0: global namespace, 10 классов.
- L1: scoped per `primary_l0`, 10 классов на каждого L0-родителя
  → 100 классов всего.
- L2: scoped per `(primary_l0, primary_l1)`, 10 классов
  → 1000 классов всего.

Bit-маски: `BIT_MASK_L0=0x000003FF`, `BIT_MASK_L1=0x000FFC00`,
`BIT_MASK_L2=0x3FF00000`.

---

## 5. Auto-allocation

См. [ADR-HTC-04](../../03-architecture/adr/ADR-HTC-04-automatic-allocation.md).

Когда LLM возвращает `Decision.NEW`:

1. Вычисляется embedding `name + " " + description`.
2. Similarity к существующим классам под parent_path:
   - `≥ SIM_REUSE (0.85)` → reuse existing bit.
   - free slot есть → allocate new bit + patch-bump version.
   - overflow → force-merge с ближайшим (см.
     [ADR-HTC-08](../../03-architecture/adr/ADR-HTC-08-similarity-overflow.md)).

---

## 6. Cascading unknown

См. [ADR-HTC-06](../../03-architecture/adr/ADR-HTC-06-cascading-unknown.md).

`unknown_at_level ∈ {None, 0, 1, 2}` — единственный флаг
завершённости классификации. Уровни ≥ `unknown_at_level` не
запрашиваются у LLM, биты не выставляются.

Downstream:

- `=0` → секция не классифицирована, RAG card не генерируется.
- `=1` → primary L0 определён, карточка с `taxonomy_path=[L0]`.
- `=2` → `taxonomy_path=[L0, L1]`.
- `None` → `taxonomy_path=[L0, L1, L2]`.

---

## 7. Seed-таксономия v1.0.0

См. [seed/taxonomy/v1_0_0.yaml](../../../seed/taxonomy/v1_0_0.yaml).

> **Замещено SETUP-13.** Идея `doc_type_hint` на узле перенесена в дерево SETUP-13 и расширена до всех онтологических полей ([ADR-HTC-10](../../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md), [SETUP-13 §8](SETUP-13-classifier-library.md#8-metadata-хинты-узлов)). Значения `domain_profile_card`, `process_card`, `reference_card` ниже не совпадают с `DocType` в `schemas/rag/ontology.py` (там `domain_profile`, а `process_card` и `reference_card` отсутствуют) и при переносе не копируются.

L0 наполнен 9 классами + 1 свободный слот:

| bit | slug | doc_type_hint |
|---|---|---|
| 0 | task | task_card |
| 1 | schema | schema_card |
| 2 | analytics | analytics_card |
| 3 | glossary | field_definition_card |
| 4 | validation_rule | validation_rule_card |
| 5 | question_template | question_template_card |
| 6 | domain_profile | domain_profile_card |
| 7 | process | process_card |
| 8 | reference | reference_card |
| 9 | — | (свободен для auto-create) |

L1 и L2 — пустые, растут автоматически.

---

## 8. Функциональные требования

- **FR-12-01**: классификация выполняется на каждой ParsedSection
  при переходе из `EXTRACTED` в `CLASSIFIED` (на этапе
  `DocumentParserOrchestrator.classify_batch`).
- **FR-12-02**: каждый уровень классификации делает ровно один
  LLM-вызов; cascading-stop пропускает уровни ≥ `unknown_at_level`.
- **FR-12-03**: bit-позиции и class_slug'и в реестре стабильны в
  рамках version'а.
- **FR-12-04**: при concurrent NEW-предложениях под одним
  parent_path advisory-lock гарантирует, что класс создаётся
  ровно один раз.
- **FR-12-05**: `taxonomy_version_id` сохраняется на каждой
  ParsedSection и каждой RAGCard.
- **FR-12-06**: bridge-таблица `section_class_tags`
  материализуется при сохранении ParsedSection.
- **FR-12-07**: thresholds (SIM_REUSE, T_SET, MIN_NEW_CLASS_CONF,
  SIM_FORCE_MERGE) загружаются из YAML и могут быть hot-reloaded
  (через config-watcher).

---

## 9. Нефункциональные требования

- **NFR-12-01 (latency)**: классификация ParsedSection p95 ≤ 6 сек
  при модели llama3.2 (3 LLM-вызова × 2 сек).
- **NFR-12-02 (throughput)**: 50 секций/мин при concurrency=3.
- **NFR-12-03 (storage)**: bitmap (4B) + indices (1B) на секцию;
  bridge-таблица ≤ 3 строк на секцию.
- **NFR-12-04 (correctness)**: precision@L0 ≥ 0.90 на goldens
  после bootstrap (50 секций); recall@L0 ≥ 0.85.
- **NFR-12-05 (no data loss)**: классификация при overflow всегда
  возвращает реальный bit (force-merge); UNKNOWN допустим только
  при `Decision.UNKNOWN` LLM.

---

## 10. Acceptance criteria

- [ ] schemas/taxonomy/ контракты валидны, тесты `tests/unit/schemas/test_taxonomy_*.py` зелёные.
- [ ] config/taxonomy/auto_allocation.yaml парсится в Pydantic-настройки.
- [ ] seed/taxonomy/v1_0_0.yaml загружается в `TaxonomyVersion` без ошибок.
- [ ] Prompt-template `prompts/classification/classify_at_level.txt` рендерится с тестовым context'ом.
- [ ] `ClassificationState` корректно сериализуется в JSON и обратно.
- [ ] Bit-маски проверены: `bit_offset(0,0)=0`, `bit_offset(1,0)=10`, `bit_offset(2,0)=20`.
- [ ] Cascading-unknown инвариант проверен в тестах
  (`unknown_at_level=1` ⇒ L1, L2 bits = 0).

---

## 11. Frontend Scope

В S0 — только подготовка контрактов. Реализация UI отложена
до S7 (TaxonomyTreeView). См. [TD-HTC-002](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md).

---

## 12. Backend Scope

S0 (этот PR-pack):
- Контракты `schemas/taxonomy/`.
- Конфиг + seed.
- Prompt-template.

S1-S10 (см. [SETUP-12.tasks.md](../../implementation-plan/SETUP-12.tasks.md)):
- `src/fe_bot/taxonomy/registry.py`, `auto_allocator.py`,
  `llm_classifier.py`, `hierarchical_classifier.py`.
- Интеграция в `DocumentParserOrchestrator`.
- Propagation в RAG card generation, retrieval, runtime.

---

## 13. DTO mapping

| Контракт | Файл | Producer | Consumer |
|---|---|---|---|
| ClassificationState | [state.py](../../../schemas/taxonomy/state.py) | HierarchicalClassifier | ParsedSection, DocTypeDetector, retrieval |
| TaxonomyBitRegistryEntry | [registry.py](../../../schemas/taxonomy/registry.py) | TaxonomyRegistry (seed + auto-allocator) | LLMClassifier (для кандидатов), retrieval (bridge) |
| TaxonomyVersion | [registry.py](../../../schemas/taxonomy/registry.py) | seed_loader, runtime bump | TaxonomyRegistry |
| Decision | [decision.py](../../../schemas/taxonomy/decision.py) | LLMClassifier (из LLM payload) | HierarchicalClassifier |
| AutoCreationRecord | [state.py](../../../schemas/taxonomy/state.py) | auto-allocator | audit logs |

---

## 14. Use cases

См. [docs/02-system/use-cases/UC-CLS-01..03.md](../use-cases/).

- UC-CLS-01: классификация секции в полностью обживённой
  таксономии (все 3 уровня успешно).
- UC-CLS-02: классификация секции, требующая создания нового L1-
  класса.
- UC-CLS-03: классификация секции, на которой LLM сказал UNKNOWN
  на L0 (cascading stop).

---

## 15. Actors

- **DocumentParserOrchestrator** — вызывает HierarchicalClassifier
  на каждом ParsedSection после извлечения.
- **HierarchicalClassifier** — оркестрирует 3 уровня.
- **LLMClassifier** — обёртка над LLMGateway для одного уровня.
- **TaxonomyRegistry** — CRUD реестра + similarity-search.
- **AutoAllocator** — gates новые классы через similarity.
- **TaxonomyClassifierAgent** — abstract user-facing role для
  AGENTS.md.

---

## 16. Связанные сервисы

- SVC-07 Document Parser Service — заменяет внутренний classifier.
- SVC-09 RAG Card Generator — читает `classification_state` для
  выбора doc_type и prompt-template.
- SVC-25 Retrieval Service — использует bitwise-фильтры.
- SVC-12 Vector Index Service — payload получает `bitmap_l0`,
  `bitmap_l1`, `bitmap_l2`, `primary_l0`, `primary_l1`.
- SVC-36 Audit Service — логирует AutoCreationRecord.

---

## 17. Связанные ADR

- [ADR-HTC-01 Open taxonomy](../../03-architecture/adr/ADR-HTC-01-open-taxonomy.md)
- [ADR-HTC-02 Bitmap layout](../../03-architecture/adr/ADR-HTC-02-bitmap-30-layout.md)
- [ADR-HTC-03 Scoped L1/L2](../../03-architecture/adr/ADR-HTC-03-scoped-l1-l2.md)
- [ADR-HTC-04 Automatic allocation](../../03-architecture/adr/ADR-HTC-04-automatic-allocation.md)
- [ADR-HTC-05 Taxonomy versioning](../../03-architecture/adr/ADR-HTC-05-taxonomy-versioning.md)
- [ADR-HTC-06 Cascading unknown](../../03-architecture/adr/ADR-HTC-06-cascading-unknown.md)
- [ADR-HTC-07 Bitwise filters](../../03-architecture/adr/ADR-HTC-07-bitwise-retrieval-filters.md)
- [ADR-HTC-08 Similarity overflow](../../03-architecture/adr/ADR-HTC-08-similarity-overflow.md)

---

## 18. Связанные тех-долги

- [TD-HTC-001](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md): re-classification.
- [TD-HTC-002](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md): Admin UI.
- [TD-HTC-003](../../tech-debt/TD-HTC-003-drift-alerts.md): drift alerts.

---

## 19. Связанные LangGraph элементы

- Setup-graph subgraph: [ClassifySectionSubgraph](../../09-langgraph/ClassifySectionSubgraph.md).
- Состояние: расширение SetupContextMemory.parsed_sections
  записями ClassificationState.

---

## 20. Связанные RAG-документы

- [docs/06-rag/taxonomy.md](../../06-rag/taxonomy.md) — методология.
- [docs/06-rag/metadata-schema.md](../../06-rag/metadata-schema.md) —
  добавление полей `taxonomy_path`, `taxonomy_version_id`,
  `taxonomy_node_id` в front_matter карточки.

---

## 21. Связанные prompt-документы

- [prompts/classification/classify_at_level.txt](../../../prompts/classification/classify_at_level.txt) —
  единый prompt для всех 3 уровней (различия в context-блоках через
  Jinja-условные).
- [docs/07-contracts/LLM-CLS-01-classify-at-level.md](../../07-contracts/LLM-CLS-01-classify-at-level.md) — контракт.

---

## 22. Связанные тесты

- `tests/unit/schemas/test_taxonomy_state.py`
- `tests/unit/schemas/test_taxonomy_registry.py`
- `tests/unit/schemas/test_taxonomy_decision.py`
- (последующие слайсы) `tests/unit/taxonomy/test_llm_classifier.py`,
  `tests/component/test_hierarchical_classifier.py`,
  `tests/integration/test_parser_with_taxonomy.py`.

---

## 23. Открытые вопросы / решения

| # | Вопрос | Решение | Источник |
|---|---|---|---|
| 1 | Closed-root vs fully open | Hybrid: L0 seeded + auto-grow L9; L1/L2 fully auto | transcript S0 |
| 2 | Multi-class L0 | Multi-tag для retrieval; drill только под primary | transcript S0 |
| 3 | Outlook on re-classification | Deferred to TD-HTC-001 | user reply |
| 4 | Embedding model | nomic-embed-text (тот же, что в проекте) | default |
| 5 | Thresholds tuning | YAML config, hot-tunable | user reply |
| 6 | Overflow strategy | force-merge with warning | user-confirmed |
