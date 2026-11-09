# ADR-HTC-03. L1/L2 классы scoped под primary L0 (primary L1)

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

[ADR-HTC-02](ADR-HTC-02-bitmap-30-layout.md) фиксирует layout 30 бит,
по 10 на уровень. Семантика L1/L2 классов может быть:

- **Global** — бит #3 уровня L1 однозначно = «ПВО» вне зависимости от
  L0. Проще для retrieval, но смысл «подкласс» теряется (ПВО — это
  подкласс чего?).
- **Scoped per parent** — бит #3 уровня L1 = «ПВО» если primary L0 =
  task, или «ETL» если primary L0 = schema. Каждый L0-родитель
  имеет собственный codebook L1.

Пользователь явно потребовал: «на каждый класс L0 своя кодировка L1
и т.д., основной контекст L0, дополнительный L1».

## Decision

L1-классы scoped под `primary_l0`. L2-классы scoped под
`(primary_l0, primary_l1)`.

Ёмкость:
- L0: 10 классов (global).
- L1: 10 × 10 = 100 классов.
- L2: 10 × 10 × 10 = 1000 классов.

Bit-registry имеет ключ `(version_id, level, parent_path, bit_index)`:

- L0: `parent_path = ""`.
- L1: `parent_path = "<l0_slug>"` (например, `"task"`).
- L2: `parent_path = "<l0_slug>.<l1_slug>"` (например, `"task.pvo"`).

При multi-class на L0 (несколько L0-бит установлено) **primary L0** —
один (argmax `confidence_per_bit`). Drill в L1 идёт только под него.
Аналогично — primary L1 → L2.

Альтернативные L0-биты сохраняются в bitmap как теги для retrieval;
их собственные L1/L2-подпути не запрашиваются (это бы потребовало
многократного LLM-вызова, чрезмерно дорого).

При близких confidence у primary и second L0 (delta <
`multi_class_delta_threshold` из config'а) секция помечается
`secondary_drill_candidate` для возможного будущего ре-drill'а
(отложено в [TD-HTC-001](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)).

## Consequences

### Положительные

- Семантика «подкласс» сохранена: бит интерпретируется в контексте
  родителя.
- Ёмкость классов растёт на два порядка (1110 вместо 30).
- Stable bit reuse: один и тот же бит L1 #3 может представлять
  «ПВО» под task и «ETL» под schema без коллизии.
- Prompt'ы LLM естественно ссылаются на `primary_l0` как контекст.

### Отрицательные

- Глобальные retrieval-запросы (например, «всё про ПВО независимо от
  L0») сложнее: нужна bridge-таблица `section_class_tags`
  (см. [ADR-HTC-07](ADR-HTC-07-bitwise-retrieval-filters.md)).
- Расшифровка bitmap'а в человекочитаемый path требует
  `(primary_l0_idx, primary_l1_idx)` + lookup в registry.
- Multi-class drilling (для всех L0-кандидатов сразу) не поддерживается
  в MVP.

## Related

- [ADR-HTC-02 bitmap layout](ADR-HTC-02-bitmap-30-layout.md)
- [ADR-HTC-07 bitwise retrieval filters](ADR-HTC-07-bitwise-retrieval-filters.md)
- [TD-HTC-001 Re-classification](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)
