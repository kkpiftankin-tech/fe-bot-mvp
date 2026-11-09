# ADR-HTC-06. Cascading unknown: нет L_k ⇒ нет L_{k+1}

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

При иерархической классификации возможны три состояния на уровне k:

1. LLM выбрал EXISTING-классы (бит выставлен).
2. LLM предложил NEW-класс (бит auto-allocated и выставлен).
3. LLM ответил UNKNOWN (либо confidence < `T_SET` / `MIN_NEW_CLASS_CONF`).

Если на L_k получили (3), что делать с L_{k+1}?

Варианты:

- Запросить L_{k+1} в надежде, что глубже LLM что-то найдёт.
  Бесполезно: контекст drill'а — это `primary_l_k`, без него codebook
  L_{k+1} не определён.
- Прервать классификацию: cascading-stop.

## Decision

**Cascading stop**: если на уровне k не определён ни один primary
класс (либо UNKNOWN, либо все confidence < `T_SET`), уровни ≥ k+1
не запрашиваются у LLM.

Состояние секции хранит `unknown_at_level ∈ {None, 0, 1, 2}`:

- `None` — классификация ещё не запускалась ИЛИ успешно прошла все 3
  уровня.
- `0` — L0 не классифицирован, L1 и L2 не запрашивались.
- `1` — L0 OK, L1 не классифицирован, L2 не запрашивался.
- `2` — L0 и L1 OK, L2 не классифицирован.

Инвариант: при `unknown_at_level = k`, биты уровней ≥ k обнулены,
`primary_l_{≥k}_idx = None`.

## Downstream-семантика

- `unknown_at_level = 0` → DocTypeDetector возвращает `None` →
  секция → INVALID_DOC_TYPE, карточка не создаётся.
- `unknown_at_level = 1` → primary L0 определён, doc_type карточки
  выбирается по L0 (через `doc_type_hint`). Карточка имеет
  `taxonomy_path = [L0_slug]`.
- `unknown_at_level = 2` → `taxonomy_path = [L0_slug, L1_slug]`.
- `None` (полная классификация) → `taxonomy_path = [L0, L1, L2]`.

## Consequences

### Положительные

- Экономия LLM-вызовов: не делаем безсмысленных запросов глубже.
- Семантически чёткое состояние: одно поле `unknown_at_level`
  заменяет 3 boolean'а.
- Возможна re-classification (см. [TD-HTC-001](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md))
  только для секций с `unknown_at_level ∈ {1, 2}` — экономия.

### Отрицательные

- Секция с `unknown_at_level = 0` не получает карточки. Это
  правильное поведение (нет смысла генерировать карточку «непонятно
  чего»), но downstream'ным метрикам важно это учитывать.
- Cascading-stop теряет возможность «угадывания»: даже если LLM
  при правильном context'е смог бы что-то ответить на L1, мы не
  попробуем.

## Related

- [ADR-HTC-02 bitmap layout](ADR-HTC-02-bitmap-30-layout.md)
- [TD-HTC-001 Re-classification](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)
- [schemas/taxonomy/state.py](../../../schemas/taxonomy/state.py)
