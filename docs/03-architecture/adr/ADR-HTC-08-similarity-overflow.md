# ADR-HTC-08. Overflow: force-merge с warning'ом

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

Cap = 10 классов на каждый `parent_path` ([ADR-HTC-02](ADR-HTC-02-bitmap-30-layout.md))
жёсткий. Когда auto-allocator получает NEW-предложение на parent_path
P, у которого уже заняты все 10 слотов, нужно решение, как
поступить с этим предложением.

Варианты:

1. **Mark as UNKNOWN на этом уровне** — теряем семантику, секция не
   получает классификации в L1/L2 даже если LLM правильно её
   распознал.
2. **Force-merge с ближайшим существующим** — переиспользуем бит
   ближайшего класса. Загрязняем его семантику, но не теряем data.
3. **Displace least-used existing** — кикаем редко используемый
   класс из реестра, отдаём его слот новому. Ломает историческую
   интерпретацию bitmap'а.
4. **Architectural change** — расширяем bit-width (`> 30` бит) или
   разносим parent_path. Не runtime, требует major version bump.

## Decision

В MVP — **force-merge с ближайшим существующим** (вариант 2).

Алгоритм при overflow:

```
neighbors = registry.list_active(version, level, parent_path)
sims = [(n, cosine(emb_new, n.embedding)) for n in neighbors]
sims.sort(key=lambda x: x[1], reverse=True)
target = sims[0]

if target.sim >= SIM_FORCE_MERGE:
    event = "class_force_merge"   # умеренно похож
else:
    event = "class_overflow"      # ни один не похож
                                  # → склейка нежелательна, но идёт

allocate_bit_for(target.entry)
log_event(event, level=level, parent_path=parent_path,
          new_proposal=proposal, target=target.entry,
          similarity=target.sim)
increment_overflow_counter(level, parent_path)
```

Различие:
- `class_force_merge` — приемлемо, warning'а нет, но событие
  фиксируется в метриках.
- `class_overflow` — alert-worthy (см.
  [TD-HTC-003](../../tech-debt/TD-HTC-003-drift-alerts.md)):
  под этим parent_path действительно нет похожих, склейка ломает
  семантику.

## Consequences

### Положительные

- Никогда не теряем data: классификация продолжается, downstream
  получает картинку.
- Reversible: если admin позже создаст admin UI
  ([TD-HTC-002](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md)),
  он сможет разделить force-merge'нутые классы обратно (через
  re-classification, [TD-HTC-001](../../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)).
- Drift visible: counter overflow + alert даёт оператору knowing,
  что parent_path требует ручной реструктуризации.

### Отрицательные

- «Молчаливая» деградация качества на perpath'ах с большим overflow.
  Митигируется метриками.
- Несколько разных NEW-предложений в течение короткого времени
  могут все смержиться с одним target'ом — реальные различия
  потеряются.

## Alternatives considered

- **Displace least-used** — отвергнуто: ломает историческую
  интерпретацию (секции, которые ссылались на kicked-out бит, станут
  читать что-то другое).
- **Bump bit-width до 64** — отвергнуто для MVP, потребует
  пересмотра schema/storage/Qdrant payload. Будет рассмотрено как
  major bump (TBD).
- **Architectural split** (разбить горячий parent_path на
  «task.combat» / «task.support») — потенциально хорошо, но
  требует human decision и code-change; отложено в
  [TD-HTC-002](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md).

## Related

- [ADR-HTC-02 bitmap layout](ADR-HTC-02-bitmap-30-layout.md)
- [ADR-HTC-04 automatic allocation](ADR-HTC-04-automatic-allocation.md)
- [TD-HTC-002 Admin UI](../../tech-debt/TD-HTC-002-taxonomy-admin-ui.md)
- [TD-HTC-003 Drift alerts](../../tech-debt/TD-HTC-003-drift-alerts.md)
