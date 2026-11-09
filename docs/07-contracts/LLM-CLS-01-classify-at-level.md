# LLM-CLS-01. Контракт LLM-вызова: классификация на одном уровне

## Producer / Consumer

- **Producer (caller)**: `LLMClassifier` (SETUP-12).
- **Consumer (callee)**: LLMGateway → Ollama (`llama3.2`).

## Endpoint / транспорт

```python
LLMGateway.generate_structured(
    prompt=rendered_prompt,
    schema=schemas.taxonomy.Decision,
    model="llama3.2",
    temperature=0.0,
)
```

`format=json` форсится gateway'ем; retry до 3 раз при невалидном
JSON.

## Input (prompt-template)

[prompts/classification/classify_at_level.txt](../../prompts/classification/classify_at_level.txt).

Параметры рендеринга:

```python
{
  "level": int,                # 0 | 1 | 2
  "primary_l0_slug": str | None,
  "primary_l0_display_ru": str | None,
  "primary_l1_slug": str | None,
  "primary_l1_display_ru": str | None,
  "also_applies_l0": list[str],
  "parent_path": str,
  "candidates": list[{
    "bit_index": int,
    "class_slug": str,
    "display_name_ru": str,
    "description": str
  }],
  "max_classes_per_level": int (10),
  "free_slots": int,
  "section_text": str
}
```

## Output (Pydantic-схема)

[schemas/taxonomy/decision.py](../../schemas/taxonomy/decision.py):

```python
class Decision(BaseModel):
    kind: Literal["existing", "new", "unknown"]
    selected: list[ExistingSelection] = []
    proposal: NewClassProposal | None = None
    overall_confidence: float  # [0, 1]
    reason: str = ""
```

### ExistingSelection

```python
{
  "bit": int,              # 0..9
  "confidence": float,     # [0, 1]
  "reason": str            # короткое обоснование
}
```

### NewClassProposal

```python
{
  "name_slug": str,             # ^[a-z0-9][a-z0-9_-]*$
  "display_name_ru": str,
  "display_name_en": str,
  "description": str            # 10..1024 символов
}
```

## Инварианты

- `kind = existing` ⇒ `selected` непусто, `proposal = null`.
- `kind = new` ⇒ `selected = []`, `proposal != null`.
- `kind = unknown` ⇒ `selected = []`, `proposal = null`, `reason`
  обязателен.
- Все `selected[*].bit` уникальны.
- Все `bit`-индексы ∈ {bit_index в `candidates`}; LLM не имеет
  права изобретать индекс вне списка.

## Обработка ошибок

| Ошибка | Поведение caller'а |
|---|---|
| `InvalidLLMOutputError` после retry | Уровень классификации помечается UNKNOWN; cascading-stop |
| `LLMUnavailableError` | Бросаем выше; orchestrator решает (отложить весь parse-job) |
| `TimeoutError` | Уровень → UNKNOWN; metric `timeout_total{level}` |
| Pydantic ValidationError post-permissive normalisation | Логируется, attempt с дополнительным «вернись к JSON» retry |

## Стоимость

Один вызов на уровень. До 3 вызовов на секцию (при cascading
прерывается раньше).

## Тестируемость

- Unit: `tests/unit/taxonomy/test_llm_classifier.py` — `FakeGateway`
  возвращает заданные Decision-сценарии.
- Component: `tests/component/test_hierarchical_classifier.py` —
  трёх-уровневая последовательность через `FakeGateway`.

## Связанные

- [TaxonomyClassifierAgent](../05-agents/taxonomy-classifier-agent.md)
- [SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md)
- [ADR-HTC-04 Automatic allocation](../03-architecture/adr/ADR-HTC-04-automatic-allocation.md)
