# Governance иерархической таксономии

> **Legacy (SETUP-12).** Ниже описана автоматическая модель реестра с битовыми масками, замещённая деревом классификаторов SETUP-13. Governance дерева SETUP-13 и его metadata-хинтов описан в конце документа: [Governance дерева классификаторов и хинтов](#governance-дерева-классификаторов-и-хинтов-setup-13).

## Принципы

В MVP — **полная автоматизация**. Никакого человеческого review для
новых классов, никакой ручной модерации между LLM-запросом и записью
в реестр.

Это сознательное решение для bootstrap-периода. По мере накопления
опыта (см. [TD-HTC-002](../tech-debt/TD-HTC-002-taxonomy-admin-ui.md))
будет добавлен admin-UI.

## Жизненный цикл реестра

### Bootstrap

1. Загрузка seed-YAML
   ([seed/taxonomy/v1_0_0.yaml](../../seed/taxonomy/v1_0_0.yaml)) в
   `TaxonomyVersion(v1.0.0, is_active=true)`.
2. L1 / L2 — пустые. L0 — 9 классов из seed.
3. Первая ParsedSection триггерит классификацию.

### Auto-allocation

Каждый раз, когда LLM возвращает `Decision.NEW` под parent_path,
auto-allocator:

1. Берёт advisory-lock `(version_id, level, parent_path)`.
2. Вычисляет embedding нового класса.
3. Сравнивает с embeddings существующих под этим parent_path.
4. Принимает решение по правилам [ADR-HTC-04](../03-architecture/adr/ADR-HTC-04-automatic-allocation.md):
   - reuse существующего бита (SIM_REUSE),
   - allocate новый бит (free slot),
   - force-merge (overflow).
5. Версия → patch bump.
6. Releases lock.

### Patch bump (runtime)

При добавлении нового бита в registry активная `TaxonomyVersion`
получает версию `vX.Y.Z+1`. Бит-позиции существующих классов не
меняются.

Старые ParsedSection, ссылающиеся на `vX.Y.Z`, продолжают читаться
корректно: registry хранит обе версии.

### Minor bump (через миграцию)

При обновлении seed-YAML (добавление новых seed-классов или
переименование display_name) релиз кода материализуется как minor
bump (`vX.Y.0 → vX.Y+1.0`).

### Major bump (TBD)

Major bump (`vX.Y.Z → vX+1.0.0`) — реструктуризация бит-позиций
или семантики. Требует full re-classification всех секций
(см. [TD-HTC-001](../tech-debt/TD-HTC-001-reclassification-after-version-bump.md)).
В MVP не выполняется.

## Что НЕ делает human

- Не одобряет новые классы (всё авто).
- Не редактирует display_name через UI (только seed-YAML +
  деплой).
- Не сливает классы вручную (auto force-merge через similarity
  при overflow).

## Что МОЖЕТ делать human

- Тюнить thresholds в [config/taxonomy/auto_allocation.yaml](../../config/taxonomy/auto_allocation.yaml).
- Наблюдать за метриками
  ([TD-HTC-003](../tech-debt/TD-HTC-003-drift-alerts.md)) и решать,
  когда пора расширять capacity.
- Готовить новые seed-классы для следующего minor bump'а.

## Drift-индикаторы (для будущего admin UI)

- `taxonomy_force_merge_total` — частота force-merge событий.
- `taxonomy_slots_used == 10` — переполнение слотов.
- `taxonomy_unknown_at_level_0_rate` — доля cascading-unknown.
- `taxonomy_new_class_total` — скорость роста реестра.

При устойчивом превышении — повод вмешаться вручную через ребилд
seed-YAML и новый minor bump.

## Анти-паттерны

- **Не «протирать» registry между релизами**: история бит-позиций
  внутри version'а — это контракт со всеми существующими секциями.
- **Не bump'ать version в обход auto-allocator'а**: ручные правки
  создадут невосстановимые рассинхронизации.
- **Не использовать display_name как stable ID**: stable — это
  `class_slug` (kebab-case). display_name можно править между
  patch'ами.

## Governance дерева классификаторов и хинтов (SETUP-13)

В отличие от SETUP-12, дерево SETUP-13 редактируют люди; авто-аллокации классов нет ([ADR-HTC-09](../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)). Metadata-хинты узлов ([SETUP-13 §8](../02-system/features/SETUP-13-classifier-library.md#8-metadata-хинты-узлов), [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)) — это не конфигурация интерфейса, а источник `doc_type` и онтологических полей всех карточек, поэтому их правка влияет на содержимое базы знаний.

- **Кто редактирует.** Роли с `KB_CLASSIFIER_WRITE` (USER, DOMAIN_EXPERT, RAG_ADMIN). Рекомендация: хинты согласует предметный эксперт вместе с RAG-архитектором; правки хинтов верхних уровней затрагивают всё поддерево.
- **Что можно задавать.** Только канонические значения: `DocType`, `ontology_v1.yaml`, закрытое множество `retrieval_purpose`. Синонимы и произвольные строки отклоняются при сохранении.
- **Где задавать.** На верхних уровнях, листья наследуют; перекрывать хинт на нижнем узле — только когда ветка действительно отличается. Источник каждого значения виден в UI (`sources`).
- **Версия.** Каждая правка меняет `version` дерева; карточка хранит `classifier_tree_version`, по которой видно, какими хинтами она получена.
- **Эффект правки.** Уже созданные карточки не меняются сами; изменение попадает в карточки при повторной генерации секций. Повторная классификация не нужна.
- **Мониторинг покрытия.** Доля листьев без `doc_type_hint` и доля секций с `DOC_TYPE_HINT_MISSING` ([SETUP-13 AC-H7](../02-system/features/SETUP-13-classifier-library.md), [SETUP-05 AC-60](../02-system/features/SETUP-05-rag-cards-generation.md)) — главный индикатор того, что дерево настроено.
- **Анти-паттерн.** Не задавать `doc_type_hint` «на всякий случай» там, где подходящего из 7 типов нет: явный отказ секции лучше карточки неверного типа.
