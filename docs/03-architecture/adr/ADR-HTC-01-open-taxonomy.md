# ADR-HTC-01. Открытая иерархическая таксономия вместо закрытого enum'а SectionType

## Status

Superseded by [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — Proposed (SETUP-12, S0)

## Context

В SETUP-01..SETUP-04 классификация секции = закрытый enum `SectionType`
(`task`, `schema`, `analytics`, `glossary`, `validation_rule`,
`question_template`, `domain_profile`, `other`, `unknown`).

Проблемы:

- Любой текст, не подходящий ни под один enum, → `UNKNOWN`.
  Downstream (`DocTypeDetector`) даёт `INVALID_DOC_TYPE` и секция не
  становится карточкой. Большая доля секций реальных документов
  попадает в эту яму.
- Плоская модель: «task ПВО» и «task навигация» неразличимы — обе
  просто `TASK`. Retrieval-фильтры на доменную специализацию
  невозможны.
- Расширение enum'а — code-change + migration; рост vocabulary
  не масштабируется.
- Семантика классификации зашита в keyword-regex'ах
  ([classifier.py](../../../src/fe_bot/setup/parser/classifier.py), [markdown_parser.py](../../../src/fe_bot/setup/parser/markdown_parser.py)), которые,
  во-первых, дублируются и расходятся, во-вторых, дают ложно-
  положительные срабатывания на общеупотребительных словах («поле»,
  «task», «rule»).

## Decision

Перейти на **открытую иерархическую таксономию** с тремя уровнями
(L0, L1, L2). Новые классы создаются автоматически по предложениям
LLM (см. [ADR-HTC-04](ADR-HTC-04-automatic-allocation.md)). L0 —
seeded (≈ legacy enum + резервный слот); L1/L2 растут в runtime.

Старый enum `SectionType` депрекейтится: derive'ится из L0 для
backward-compat (см. ADR-HTC-05).

## Consequences

### Положительные

- Классификация перестаёт быть «бутылочным горлышком». Любая
  секция получает специфичный путь, даже если в seed-таксономии
  такого класса не было.
- Retrieval и runtime-агенты могут фильтровать по уровням
  специфичности.
- Качество классификации привязано к LLM, а не к keyword'ам;
  улучшается вместе с моделью.
- Документация — не от человека-куратора, а от семантики самих
  документов.

### Отрицательные

- Стоимость: 1-3 LLM-вызова на секцию (вместо нулевой стоимости
  rule-based).
- Vocabulary explosion возможен; митигируется через
  [ADR-HTC-04](ADR-HTC-04-automatic-allocation.md) (similarity-gate +
  cap=10 на уровень + force-merge).
- Тяжелее объяснить пользователю, чем «task vs schema»; нужен
  tree-view в UI и понятные display_name.
- Отсутствие human review создаёт риск «молчаливой деградации» —
  митигируется метриками и алёртами
  ([TD-HTC-003](../../tech-debt/TD-HTC-003-drift-alerts.md)).

### Нейтральные

- Сохраняем backward-compat ParsedSection через derive (см.
  [ADR-HTC-05](ADR-HTC-05-taxonomy-versioning.md)) — миграция
  in-place, без переноса данных.

## Alternatives considered

- **Расширить enum**: добавить ещё 10-20 значений вручную. Не решает
  vocabulary explosion и не даёт иерархии.
- **Faceted classification** (несколько ортогональных деревьев). Не
  matches mental model пользователя; сложный UI; merge с
  DocTypeDetector нетривиален.
- **DAG / poly-hierarchy** (узел с несколькими родителями). Слишком
  сложно для MVP; не используется на этапе нашего масштаба.
- **Tag cloud** (без иерархии). Теряем drill-down; не подходит для
  production-retrieval.

Подробный сравнительный анализ — в protocol-обсуждении S0
(см. transcript review, июнь 2026).

## Related

- [SETUP-12 feature doc](../../02-system/features/SETUP-12-llm-taxonomy-classification.md)
- [ADR-HTC-02 bitmap layout](ADR-HTC-02-bitmap-30-layout.md)
- [ADR-HTC-04 automatic allocation](ADR-HTC-04-automatic-allocation.md)
- [ADR-HTC-06 cascading unknown](ADR-HTC-06-cascading-unknown.md)
