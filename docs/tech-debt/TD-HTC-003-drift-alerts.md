# TD-HTC-003 — Drift-метрики и автоматические алёрты по таксономии

## Status

Open (deferred from S0 of SETUP-12)

## Context

Auto-allocation + force-merge без human review (см.
[ADR-HTC-04](../03-architecture/adr/ADR-HTC-04-automatic-allocation.md),
[ADR-HTC-08](../03-architecture/adr/ADR-HTC-08-similarity-overflow.md))
безопасны для bootstrap, но «молча деградировать» — это анти-паттерн
для production. Нужны метрики и алёрты, чтобы оператор узнавал о
проблеме до того, как пользователи увидят странную классификацию.

## Что отложено

### Метрики (Prometheus / `src/fe_bot/observability/metrics.py`)

- `taxonomy_classification_total{level, outcome}` — outcome ∈
  `existing | new | force_merge | unknown`.
- `taxonomy_force_merge_total{level, parent_path}` — счётчик каждого
  force-merge события.
- `taxonomy_new_class_total{level, parent_path}` — счётчик
  auto-created классов.
- `taxonomy_slots_used{level, parent_path}` — gauge, сколько из 10
  слотов занято.
- `taxonomy_classification_latency_seconds{level}` — histogram.
- `taxonomy_llm_unknown_total{level}` — счётчик cascading-unknown.

### Алёрты

- `force_merge_total{parent_path=X}` > 5 за 24 ч → подозрение, что под
  parent_path X пора расширять capacity (ручная реструктуризация).
- `slots_used == 10` на любом `parent_path` → wake-up для admin'а.
- `unknown_at_level_0_rate` > 30% за час → возможен сбой LLM или
  деградация качества классификации.
- `new_class_total` устойчиво > 5/ч после первых N setup_job'ов →
  vocabulary explosion подозревается, требуется ручной анализ.

### Дашборд

Grafana JSON в `docs/observability/dashboards/taxonomy-health.json`:
- per-level slot utilization
- top-10 most-used classes
- top-10 force-merge hotspots
- proposal/creation rate за час/день

## Триггеры на пересмотр

- Первый production deploy SETUP-12.
- Появление инцидента, где классификация молча сломалась.

## Owner

TBD. Кандидаты: SRE + RAG-quality.

## Related

- [SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md)
- [TD-HTC-002 Admin UI](TD-HTC-002-taxonomy-admin-ui.md)
- [ADR-HTC-08 Similarity overflow](../03-architecture/adr/ADR-HTC-08-similarity-overflow.md)
