# ADR-HTC-02. 30-битный layout классификации (3 уровня × 10 классов)

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

Иерархическая классификация (см. [ADR-HTC-01](ADR-HTC-01-open-taxonomy.md))
требует компактного storage-формата состояния, который:

- Поддерживает multi-membership (секция может относиться к нескольким
  L0-классам одновременно).
- Допускает быстрые битовые фильтры в retrieval.
- Имеет фиксированный размер для индексации в БД и в payload
  Qdrant.
- Естественно выражает «classification is incomplete» (нулевое
  состояние).

## Decision

Использовать 30-битный bitmap (в `uint32`), разбитый на три зоны
по 10 бит:

```
bit position : 29 ─── 20 | 19 ─── 10 |  9 ─── 0
                L2 (10)    L1 (10)     L0 (10)
```

- `L0` — биты 0..9, **global namespace** (один общий codebook на 10
  корневых классов).
- `L1` — биты 10..19, **scoped namespace** под `primary_l0` (одни
  и те же 10 битов читаются по разным codebook'ам в зависимости от
  того, какой L0-класс выбран primary'м).
- `L2` — биты 20..29, **scoped namespace** под `(primary_l0,
  primary_l1)`.

Биты 30..31 в `uint32` остаются неиспользованными (зарезервированы).

Бит-маски (см. [schemas/taxonomy/state.py](../../../schemas/taxonomy/state.py)):
- `BIT_MASK_L0 = 0x000003FF`
- `BIT_MASK_L1 = 0x000FFC00`
- `BIT_MASK_L2 = 0x3FF00000`

Полное состояние секции:

```python
classification_bitmap : uint32  (30 эффективных бит)
primary_l0_idx        : int|None (0..9)
primary_l1_idx        : int|None (0..9)
```

Ёмкость классов:

- L0: 10
- L1: 10 классов × 10 L0-родителей = 100
- L2: 10 × 100 = 1000

Итого 1110 возможных классов, занимающих 30 бит.

## Consequences

### Положительные

- `bitmap = 0` ⇒ unknown (естественное начальное состояние).
- Multi-membership на L0 свободно: один и тот же bitmap может иметь
  несколько L0-бит установленными (для retrieval-тегирования).
- Битовые фильтры в БД / Qdrant дешёвы.
- 4 байта на секцию + два uint4 на indices.
- Совместимо с PostgreSQL `INTEGER` и Qdrant payload `int`.

### Отрицательные

- Жёсткий cap = 10 на уровень. Расширение требует major-version-bump'а
  схемы (бит-разрядность > 30) — см. [ADR-HTC-05](ADR-HTC-05-taxonomy-versioning.md).
- Scoped namespace L1/L2 усложняет global retrieval-запросы (нужна
  bridge-таблица `section_class_tags`).
- Биты не самодокументирующиеся: декодирование требует
  обращения в `taxonomy_bit_registry` для конкретной версии.

### Нейтральные

- Multi-class L0 фиксируется на retrieval-level, но drill в L1/L2
  идёт только под primary L0 (см.
  [ADR-HTC-03](ADR-HTC-03-scoped-l1-l2.md)).

## Alternatives considered

- **List[str] materialized path** (`["task", "pvo", "tracking"]`). Гибче в
  плане глубины, но дороже для retrieval (требует параллельной
  индексации); миграция тяжелее.
- **Closure table**. Поддерживает DAG; для строго-дерева
  избыточно.
- **Global namespace L1/L2** (бит #3 L1 = «ПВО» независимо от L0).
  Проще, но теряет семантику «дополнительный контекст к L0».
  Отвергнуто пользователем — см. transcript S0.

## Related

- [ADR-HTC-01 Open taxonomy](ADR-HTC-01-open-taxonomy.md)
- [ADR-HTC-03 Scoped L1/L2](ADR-HTC-03-scoped-l1-l2.md)
- [ADR-HTC-05 Taxonomy versioning](ADR-HTC-05-taxonomy-versioning.md)
- [schemas/taxonomy/state.py](../../../schemas/taxonomy/state.py)
