# ADR-HTC-04. Автоматическое создание классов через similarity-gate

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

[ADR-HTC-01](ADR-HTC-01-open-taxonomy.md) фиксирует открытую таксономию:
LLM может предложить новый класс. Открытый вопрос: как этот новый
класс материализуется в реестре?

Варианты:

- **Human review** — proposal queue, admin approve'ит каждый новый
  класс. Безопасно, но требует постоянного оператора и тормозит
  bootstrap.
- **Automatic** — proposal сразу становится записью в реестре.
  Быстро, но риск vocabulary explosion и дубликатов-синонимов.

Пользователь явно потребовал: «всё должно быть автоматически, новые
классы должны сохраняться».

## Decision

Все новые классы создаются автоматически на pipeline'е классификации
(без human review). Защита от vocabulary explosion и дубликатов —
через **similarity-gate**.

### Алгоритм allocation на уровне k под parent_path P

Когда LLM возвращает `Decision(kind=NEW, proposal=...)`:

```
emb_new = embed(proposal.display_name_ru + " " + proposal.description)
neighbors = registry.list_active(version, k, P)
sims = [(n, cosine(emb_new, n.embedding)) for n in neighbors]
sims.sort(key=lambda x: x[1], reverse=True)

if sims and sims[0].sim >= SIM_REUSE:
    # переформулировка существующего класса
    return BitAllocation(reuse=sims[0].entry, source="similarity_reuse")

if free_slot_available(version, k, P):
    new_bit = allocate_next_free_slot(version, k, P)
    create_registry_entry(
        new_bit, proposal,
        embedding=emb_new,
        auto_created=True,
        created_by_section=section_id,
    )
    bump_taxonomy_version_patch()
    return BitAllocation(new=new_bit, source="auto_create")

# overflow: 10 слотов заняты, ни один не похож достаточно сильно
target = sims[0].entry if sims else any_active(version, k, P)
log_event("class_overflow" if not sims or sims[0].sim < SIM_FORCE_MERGE
          else "class_force_merge", ...)
return BitAllocation(reuse=target, source="force_merge")
```

### Параметры (config/taxonomy/auto_allocation.yaml)

- `SIM_REUSE = 0.85` — переиспользование существующего бита при
  семантическом дубликате.
- `SIM_FORCE_MERGE = 0.70` — порог «достаточно похоже для склейки»
  при overflow.
- `MIN_NEW_CLASS_CONF = 0.65` — нижний порог `overall_confidence`
  у NEW-предложения. Ниже → переинтерпретация как UNKNOWN.

Значения тюнятся по результатам испытаний без code-change.

### Concurrency

Registry-уровень advisory-lock на ключ `(version_id, level,
parent_path)`. Параллельные классификации не создают дубликаты:
вторая после lock'а увидит уже добавленный класс и попадёт на путь
similarity_reuse.

## Consequences

### Положительные

- Bootstrap не требует ручного куратора.
- Дубликаты-синонимы отсекаются на уровне embedding-similarity.
- Overflow обрабатывается без data loss (force-merge, не UNKNOWN).
- Idempotent при retry классификации (cache по hash(content) + lock
  на parent_path).

### Отрицательные

- Качество классификации зависит от качества embedding-модели.
- Возможна "молчаливая" склейка двух полу-различных классов через
  force-merge.
- При плохой LLM (галлюцинации) реестр может «зашуметь» новыми
  классами; митигируется `MIN_NEW_CLASS_CONF` и
  [TD-HTC-003](../../tech-debt/TD-HTC-003-drift-alerts.md) метриками.

### Нейтральные

- Admin UI (см. [TD-HTC-002](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md))
  даст возможность пост-фактум править реестр, но не блокирует
  MVP-релиз.

## Alternatives considered

- **Human review queue** — отложено как техдолг ([TD-HTC-002](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md)).
- **Frequency-gate** (создавать только после N сходных proposal'ов) —
  усложняет логику; в MVP не нужно, потому что similarity-gate уже
  даёт дедупликацию.
- **Displace least-used** при overflow — рискованно, ломает
  историческую интерпретацию bitmap'а.

## Related

- [ADR-HTC-01 Open taxonomy](ADR-HTC-01-open-taxonomy.md)
- [ADR-HTC-08 Similarity overflow](ADR-HTC-08-similarity-overflow.md)
- [TD-HTC-002 Admin UI](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md)
- [TD-HTC-003 Drift alerts](../../tech-debt/TD-HTC-003-drift-alerts.md)
- [config/taxonomy/auto_allocation.yaml](../../../config/taxonomy/auto_allocation.yaml)
