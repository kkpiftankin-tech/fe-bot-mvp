# ADR-HTC-05. Версионирование таксономии и переезд между версиями

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

При авто-allocation'е реестр меняется в runtime'е. Секции,
классифицированные в момент времени `t1`, читают bitmap в семантике
реестра `t1`. Если в момент `t2` бит был переаллоцирован, старые
секции стали бы интерпретироваться по-другому. Это недопустимо.

Также: будут эволюционные изменения структуры (seed-добавления,
переименование slug'ов, реструктуризация parent_path'ов), которые
тоже нужно отслеживать.

## Decision

Каждый bit в реестре привязан к `taxonomy_version_id` (semver).
ParsedSection и RAGCard несут `taxonomy_version_id`, под которой
были классифицированы.

### Bump-политика

- **Patch** (`v1.0.0` → `v1.0.1` → ...): авто-allocation одного или
  нескольких новых классов. Бит-позиции существующих классов не
  меняются. Старые секции, читающие `v1.0.0`, корректно работают:
  registry хранит все версии, lookup идёт по их `version_id`.
- **Minor** (`v1.0.x` → `v1.1.0`): seed-добавления через миграцию
  (новый seed-class, deprecate существующего через `merged_into`).
  Также рестарт сервиса с обновлённым seed-YAML.
- **Major** (`v1.x.y` → `v2.0.0`): реструктуризация семантики бит-
  позиций (например, перенос parent_path'ов). Требует full
  re-classification всех секций.

В MVP: только patch и minor. Major откладывается до фактической
потребности.

### Идентификация

```
taxonomy_version_id : VARCHAR(32) ~ "v<major>.<minor>.<patch>"
```

Активная версия — одна в любой момент. Storage:

```sql
CREATE TABLE taxonomy_versions (
    version_id  VARCHAR(32) PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT false
);

CREATE UNIQUE INDEX one_active_version
    ON taxonomy_versions ((1)) WHERE is_active = true;
```

### Backward-compat для SectionType enum

ParsedSection в дальнейшем имеет:
- Новое: `classification_state: ClassificationState`.
- Старое: `section_type: SectionType` — становится derived-property:
  возвращает `SectionType` соответствующего L0-slug, если найден
  legacy mapping; иначе `SectionType.UNKNOWN`.

Это позволяет SETUP-01..SETUP-11 работать без правок до тех пор,
пока их по очереди не отрефакторят на новые таксономические поля.

## Consequences

### Положительные

- Bitmap-семантика стабильна в рамках version'а.
- Auto-allocation безопасен: patch-bump не ломает существующие
  секции.
- Эволюция taxonomy не требует выключения сервиса.

### Отрицательные

- Хранение нескольких версий реестра увеличивает storage.
- Re-classification на новой major-версии — отдельный batch-job
  ([TD-HTC-001](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)).
- Frontend должен учитывать `taxonomy_version_id` секции (для
  правильного отображения display_name'а).

## Related

- [ADR-HTC-02 bitmap layout](ADR-HTC-02-bitmap-30-layout.md)
- [ADR-HTC-04 automatic allocation](ADR-HTC-04-automatic-allocation.md)
- [TD-HTC-001 Re-classification](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)
