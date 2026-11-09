# TaxonomyClassifierAgent

## Назначение

Иерархическая LLM-классификация одной секции в bitmap-таксономии.
Выполняется в Setup-stage между извлечением секций (SETUP-04) и
генерацией RAG-карточек (SETUP-05). Заменяет rule-based
`SectionClassifier`.

## Inputs

```python
section: ParsedSection
parent_path: str         # "" / "task" / "task.pvo"
level: int               # 0 | 1 | 2
candidates: list[TaxonomyBitRegistryEntry]   # текущие классы под parent_path
context_l0: str | None   # primary L0 slug, для level >= 1
context_l1: str | None   # primary L1 slug, для level = 2
free_slots: int          # сколько слотов из 10 свободно
```

## Output

```python
Decision(
    kind = DecisionKind.EXISTING | NEW | UNKNOWN,
    selected: list[ExistingSelection] = [],
    proposal: NewClassProposal | None = None,
    overall_confidence: float,
    reason: str
)
```

См. [contracts/LLM-CLS-01-classify-at-level.md](../07-contracts/LLM-CLS-01-classify-at-level.md).

## Prompt

[prompts/classification/classify_at_level.txt](../../prompts/classification/classify_at_level.txt)
— один template для всех уровней, различия в context-блоках через
Jinja-условные.

## Поведение

### Уровень 0

- Контекст: только сам текст секции.
- Кандидаты: 9 классов из seed + 1 свободный слот (или 10 после
  первого auto-create).
- Multi-class разрешён: можно выбрать несколько L0.

### Уровень 1

- Контекст: primary L0 + (optional) другие L0-биты.
- Кандидаты: scoped под primary L0. На старте — пусто, растут
  автоматически.
- Multi-class разрешён.

### Уровень 2

- Контекст: primary L0 + primary L1.
- Кандидаты: scoped под `(primary_l0, primary_l1)`.

### Возврат UNKNOWN

LLM должен возвращать UNKNOWN если:
- Текст слишком общий / случайный / нерелевантный.
- Ни один существующий класс не подходит И нет уверенности в
  новой формулировке.

Никакой cascading-unknown ниже primary'я не запрашивается.

### Возврат NEW

LLM должен возвращать NEW если:
- Видит явный паттерн, не покрытый существующими.
- `overall_confidence >= MIN_NEW_CLASS_CONF` (0.65) — иначе
  использует UNKNOWN.

После NEW происходит auto-allocation через similarity-gate
([ADR-HTC-04](../03-architecture/adr/ADR-HTC-04-automatic-allocation.md));
LLM **не управляет** тем, создастся ли реально новый бит или
произойдёт reuse/force-merge.

## Confidence требования

- Для каждого `ExistingSelection` LLM указывает `confidence ∈ [0, 1]`.
- `overall_confidence` — общая уверенность в decision.
- Бит реально выставляется, только если `confidence >= T_SET (0.60)`.
  Иначе значение сохраняется в `confidence_per_bit`, но bitmap
  остаётся нетронутым.

## Ошибки и retry

- Невалидный JSON → gateway-level retry (до 3 раз).
- После 3 неудачных попыток → классификация на этом уровне
  считается `UNKNOWN`; cascading-stop.
- Timeout → классификация на этом уровне `UNKNOWN`.

## LangGraph integration

См. [ClassifySectionSubgraph](../09-langgraph/ClassifySectionSubgraph.md).

## Метрики

См. [TD-HTC-003](../tech-debt/TD-HTC-003-drift-alerts.md).
