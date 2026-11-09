# TD-HTC-002 — Admin UI для управления таксономией

## Status

Open (deferred from S0 of SETUP-12)

## Context

В MVP SETUP-12 вся работа с таксономией — авто:

- Auto-allocation бит при первом LLM-предложении (см.
  [ADR-HTC-04](../03-architecture/adr/ADR-HTC-04-automatic-allocation.md)).
- Similarity-gate решает, переиспользовать ли существующий класс или
  создать новый.
- Overflow → force-merge с warning'ом в лог.

Это работает для bootstrap-периода, но через 3-6 месяцев накопится
потребность в **ручных операциях** над таксономией.

## Что отложено

UI и API для kb_admin'а:

- Просмотр дерева актуальной taxonomy_version: L0 → L1 → L2 (с
  фильтром по `parent_path`).
- Per-bit статистика: `usage_count`, дата создания, секции-источники.
- Ручной **merge** двух классов (одного уровня) в один. Включая
  ре-классификацию связанных секций.
- Ручное **deprecate** класса (`status=deprecated_merged`, секции
  получают `redirect_to` bit).
- Просмотр overflow-warnings (см. [TD-HTC-003](TD-HTC-003-drift-alerts.md))
  и принятие решения: «accept force-merge», «promote new class
  (displace одного из 10)», «split parent_path на два».
- История изменений: какой setup_job триггернул auto-create какого
  класса.

## Триггеры на пересмотр

- Первое появление overflow-warning'а на горячем `parent_path`.
- Жалоба пользователя на «непонятный класс».
- Появление двух явных синонимов в реестре (LLM создал оба до того,
  как embedding'и стабилизировались).

## Owner

TBD. Кандидаты: команда RAG-quality + frontend.

## Related

- [SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md)
- [TD-HTC-001 Re-classification](TD-HTC-001-reclassification-after-version-bump.md)
- [TD-HTC-003 Drift alerts](TD-HTC-003-drift-alerts.md)
