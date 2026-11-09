# TD-HTC-001 — Re-classification после bump'а taxonomy_version

## Status

Open (deferred from S0 of SETUP-12)

## Context

Когда L1/L2 уровни иерархической таксономии пополняются авто-созданными
классами (см. [SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md)),
существующие секции с `unknown_at_level >= 1` остаются с тем состоянием,
в котором были классифицированы. Они могли бы получить точную
классификацию, если бы их прогнали через LLM повторно после появления
новых классов.

## Что отложено

- Background job по периодическому re-classify секций с
  `unknown_at_level ∈ {1, 2}`.
- Re-classify не пересчитывает уровень 0 (он seeded, не меняется
  через auto-allocation).
- Триггеры: либо после N auto-create событий на конкретном
  `parent_path`, либо по расписанию.
- Учёт стоимости LLM-вызовов; дедупликация по `hash(content)` секции.
- Учёт сохранения `taxonomy_version_id` секции и инкремент при
  пересмотре.
- Метрика `taxonomy_reclassification_runs_total`.

## Влияние на качество

В MVP, секции, попавшие в момент пустого/неполного `parent_path`,
останутся «недо-классифицированными» до явного триггера. Это норма
для bootstrap-периода, но через 1-2 месяца после ввода в эксплуатацию
накопится критическая масса, ради которой стоит запустить
re-classification.

## Триггеры на пересмотр

- Жалобы пользователей: «эти секции должны были классифицироваться лучше».
- Метрика `unknown_at_level >= 1` устойчиво > 30% от всех секций.
- Появление > 50 auto-created классов на L1/L2.
- Появление admin-UI (см. [TD-HTC-002](TD-HTC-002-taxonomy-admin-ui.md)) —
  ручной запуск re-classify станет дешёвым операционным действием.

## Owner

TBD. Кандидаты: команда RAG-quality.

## Related

- [SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md)
- [ADR-HTC-04 Automatic allocation](../03-architecture/adr/ADR-HTC-04-automatic-allocation.md)
- [ADR-HTC-05 Taxonomy versioning](../03-architecture/adr/ADR-HTC-05-taxonomy-versioning.md)
