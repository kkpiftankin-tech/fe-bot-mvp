# ADR-HTC-07. Bitwise-фильтры в retrieval + bridge-таблица для глобальных запросов

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

Bitmap-классификация (см. [ADR-HTC-02](ADR-HTC-02-bitmap-30-layout.md))
позволяет дешёво проверять «есть ли у секции/карточки выставленный
бит X»:

```sql
WHERE classification_bitmap & (1 << X) != 0
```

Но scoped L1/L2 (см. [ADR-HTC-03](ADR-HTC-03-scoped-l1-l2.md))
делают «глобальные» запросы вида «все секции о ПВО независимо от
primary L0» сложнее: бит L1 #3 имеет разный смысл для разных
`primary_l0`.

## Decision

### Локальные фильтры (быстрые)

Используем bitwise-выражения напрямую. Примеры:

```sql
-- Любая секция, у которой бит "task" установлен на L0
WHERE classification_bitmap & (1 << 0) != 0

-- Секции, где task — primary
WHERE primary_l0_idx = 0

-- task.pvo (с учётом primary L0 = task)
WHERE primary_l0_idx = 0
  AND classification_bitmap & (1 << 10) != 0   -- L1 bit #0 в scope task

-- task.pvo.tracking
WHERE primary_l0_idx = 0
  AND primary_l1_idx = 0
  AND classification_bitmap & (1 << 20) != 0   -- L2 bit #0 в scope task.pvo

-- OR-фильтр на L0: task OR analytics
WHERE classification_bitmap & ((1<<0) | (1<<2)) != 0
```

В Qdrant аналогичные фильтры через payload `bitmap_l0`, `bitmap_l1`,
`bitmap_l2` (для удобства храним 3 ints отдельно) и `primary_l0`,
`primary_l1`.

### Глобальные фильтры (через bridge-таблицу)

Для запросов «всё про ПВО независимо от primary L0» вводим
`section_class_tags`:

```sql
CREATE TABLE section_class_tags (
    section_id      VARCHAR(64),
    taxonomy_version VARCHAR(32),
    level           SMALLINT,
    parent_path     VARCHAR(128),
    class_slug      VARCHAR(64),
    is_primary      BOOLEAN,
    PRIMARY KEY (section_id, taxonomy_version, level, parent_path, class_slug)
);
CREATE INDEX ON section_class_tags (level, parent_path, class_slug);
CREATE INDEX ON section_class_tags (level, class_slug);  -- глобальный поиск
```

Эта таблица **derived** из bitmap'а: триггер или application-level
sync при сохранении ParsedSection материализует записи.

Пример глобального запроса:

```sql
-- Все секции с классом "pvo" на уровне 1, независимо от parent_path
SELECT section_id FROM section_class_tags
WHERE level = 1 AND class_slug = 'pvo';
```

## Consequences

### Положительные

- Дешёвые локальные фильтры в PG и Qdrant.
- Один универсальный bridge-индекс на нетривиальные глобальные запросы.
- Bitmap остаётся каноническим источником истины; bridge — derived.

### Отрицательные

- Двойная запись (bitmap + bridge) → возможна рассинхронизация.
  Митигируется триггером (DB-level) или единым `Repository.save`.
- Bridge-таблица ~ 3× размер ParsedSection (3 записи на секцию в
  среднем). Допустимо для проекта нашего масштаба.

## Related

- [ADR-HTC-02 bitmap layout](ADR-HTC-02-bitmap-30-layout.md)
- [ADR-HTC-03 scoped L1/L2](ADR-HTC-03-scoped-l1-l2.md)
- [docs/06-rag/taxonomy.md](../../06-rag/taxonomy.md)
