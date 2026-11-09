# ClassifySectionSubgraph

Subgraph для иерархической классификации одной секции. Часть
Setup-graph'а, вызывается в этапе `parse_documents`.

## State (sub-state в SetupContextMemory)

```python
class ClassifyState(TypedDict):
    section: ParsedSection
    taxonomy_version_id: str
    state: ClassificationState   # mutable, накапливается уровнями
    last_decision: Decision | None
    error: str | None
```

## Узлы (nodes)

```
                ┌────────────────────┐
   start  ──►   │ classify_l0        │
                │  - get candidates  │
                │  - llm_classify    │
                │  - apply_bits      │
                │  - pick primary_l0 │
                └─────────┬──────────┘
                          │
              ┌───────────┴────────────┐
              │                        │
         decision = unknown         decision = existing/new
              │                        │
              ▼                        ▼
       set unknown_at_level=0   ┌────────────────────┐
              │                  │ classify_l1        │
              ▼                  └─────────┬──────────┘
            end                            │
                                ┌──────────┴───────────┐
                                │                      │
                          decision = unknown       continue
                                │                      │
                                ▼                      ▼
                         unknown_at_level=1     ┌──────────────┐
                                │                │ classify_l2  │
                                ▼                └──────┬───────┘
                              end                       │
                                              ┌─────────┴────────┐
                                              │                  │
                                       decision = unknown    continue
                                              │                  │
                                              ▼                  ▼
                                       unknown_at_level=2  full classified
                                              │                  │
                                              ▼                  ▼
                                            end                end
```

### classify_l0

Вход: `section`, `taxonomy_version_id`.
Выход: `state.classification_bitmap` (биты L0), `primary_l0_idx`,
`confidence_per_level[0]`.

Шаги:
1. `registry.list_active(version, 0, "")` → candidates.
2. `llm_classifier.classify(section, level=0, candidates, ...)`.
3. Если `Decision.UNKNOWN` → `state.unknown_at_level = 0`, end.
4. Если `Decision.NEW` → `auto_allocator.allocate(decision.proposal)`.
5. Apply bits, pick primary_l0_idx.

### classify_l1

Вход: state с L0 + primary_l0_idx.
Выход: бит L1, primary_l1_idx, confidence_per_level[1].

Шаги аналогичны L0, но с `parent_path = primary_l0_slug` и
дополнительным context в prompt'е.

### classify_l2

Вход: state с L0+L1 + primary'и.
Выход: бит L2, confidence_per_level[2].

## Переходы (edges)

| From | To | Условие |
|---|---|---|
| start | classify_l0 | always |
| classify_l0 | end | last_decision.kind == unknown OR no L0 bits set |
| classify_l0 | classify_l1 | primary_l0_idx is set |
| classify_l1 | end | last_decision.kind == unknown OR no L1 bits set |
| classify_l1 | classify_l2 | primary_l1_idx is set |
| classify_l2 | end | always |

## Human-in-the-loop

В MVP отсутствует (см. governance, full auto). После
[TD-HTC-002](../tech-debt/TD-HTC-002-taxonomy-admin-ui.md):
после classify_l0/L1/L2 может быть optional HITL-нод
`maybe_pause_for_review`, активируемый при overflow-warning'е
конкретной секции.

## Error handling

- `LLMUnavailableError` в любом узле → весь subgraph возвращает
  state с `error` полем; вызывающий код решает (skip section,
  retry, fail job).
- Невалидный JSON / Decision-валидация → внутри `classify_l*`
  обрабатывается через gateway-retry; если все попытки провалены —
  считаем UNKNOWN.

## Метрики

См. [TD-HTC-003](../tech-debt/TD-HTC-003-drift-alerts.md).

- `taxonomy_classification_latency_seconds{level}` — histogram.
- `taxonomy_classification_total{level, outcome}`.

## Тесты

- `tests/component/test_classify_section_subgraph.py` — 3 happy
  path сценария: full success, unknown@L0, unknown@L1.
- `tests/integration/test_parser_with_classify_subgraph.py` —
  e2e через parser orchestrator.
