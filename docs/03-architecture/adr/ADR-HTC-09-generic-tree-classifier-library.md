# ADR-HTC-09. Библиотека классификаторов: универсальное дерево вместо 30-битной маски

## Status

Accepted (замещает [ADR-HTC-01](ADR-HTC-01-open-taxonomy.md)..[ADR-HTC-08](ADR-HTC-08-similarity-overflow.md))

## Context

SETUP-12 спроектирован под 3-уровневую иерархию с capacity 10 классов
на уровень (см. [ADR-HTC-02](ADR-HTC-02-bitmap-30-layout.md)): формат
хранения — 30-битный `classification_bitmap` (`uint32`), где позиция
бита = `level * 10 + bit_index`.

На вход поступило дерево прикладной классификации АСУ
(`incoming-docs/raw/Классификатор.md`): **6 уровней**, **906 узлов**
(12 → 64 → 336 → 345 → 122 → 27 по уровням), у раскрытых узлов —
**5–15 дочерних элементов**. Это не помещается в 30-битную схему ни
по глубине (6 > 3), ни по ширине (до 15 > 10 на уровень) — потребовался
бы major-version bump бит-разрядности (см. [ADR-HTC-05](ADR-HTC-05-taxonomy-versioning.md))
до величины, которая перестаёт быть компактной (при 15 детях/уровень и
6 уровнях — под сотню бит на путь, поля переменной ширины на каждом
уровне, что убивает саму идею fixed-width bitmap).

Также сменилось назначение: SETUP-12 проектировался только под
классификацию *секций документа* для RAG card generation. Новая
библиотека классификаторов — **отдельный конфигурируемый ресурс**:
дерево классов создаётся/редактируется человеком (или импортируется
из внешнего таксономического документа), у каждого узла с детьми
есть промпт для маленькой LLM, определяющий переход на следующий
уровень. Использование этого дерева для классификации фрагментов
документа — последующий этап (см. §"Открытые вопросы"). Как результат классификации превращается в metadata карточек и чанков, решено в [ADR-HTC-10](ADR-HTC-10-classification-hints-single-source.md).

## Decision

1. **Модель данных — произвольное дерево**, не bitmap:
   `ClassifierNode(node_id, parent_id, level, name, description,
   children_ids, prompt_template, is_leaf)`. Глубина и ширина не
   ограничены схемой (bounds — только UX-рекомендации 5–15 детей,
   не hard constraint).
2. **Промпт — не per-node свободный текст, а рендер общего шаблона**
   (аналог `prompts/classification/classify_at_level.txt` из
   SETUP-12), параметризованного именем/описанием узла и списком
   детей. Это даёт единообразные, поддерживаемые промпты для 200+
   разветвлённых узлов без ручного набора или дорогих LLM-вызовов на
   каждый узел. `prompt_template` на узле — **опциональный override**
   для случаев, когда общий шаблон не подходит.
3. **Версионирование по всему дереву** (snapshot), не per-bit
   patch-bump — дерево редактируется людьми через UI, а не
   auto-allocator'ом в рантайме, поэтому page-level versioning
   (SETUP-12 ADR-HTC-05) избыточен для этого сценария.
4. Существующая инфраструктура SETUP-12 (`schemas/taxonomy/`,
   `src/fe_bot/taxonomy/`, `TaxonomyTreeView.tsx`, retrieval
   bitwise-фильтры) **не удалена**, но классификация секций
   документа переключена: `FE_BOT_TAXONOMY_MODE=llm` теперь строит
   `ClassifierTreeSectionClassifier` (новое дерево) вместо legacy
   `HierarchicalSectionClassifier` (bitmap). См. §"Реализовано" ниже.

## Consequences

### Положительные

- Глубина/ширина дерева не ограничены схемой — 6 уровней и 15 детей
  укладываются без компромиссов.
- Дерево — человекочитаемая, редактируемая структура (id/parent_id),
  не bitmap — не нужен реестр для расшифровки бит.
- Общий prompt-шаблон вместо per-node текста — 906 узлов не требуют
  906 отдельных промптов, и обновление формулировки правила
  применяется сразу ко всем узлам.

### Отрицательные

- Теряется compact bitwise retrieval filtering (SETUP-12 ADR-HTC-07) —
  для этого дерева multi-membership и bitwise-фильтры пока не
  спроектированы; при переводе секций на новую классификацию это
  нужно спроектировать заново (path-based фильтры вместо битовых масок).
- Два независимых дерева классификации одновременно в проекте до
  момента переключения — временная сложность, которую нужно
  разрешить явным следующим ADR при переносе классификации секций.

## Реализовано

- `FragmentClassifier` (`src/fe_bot/classifier/fragment_classifier.py`)
  — многоуровневый обход дерева с реальным `fragment_text` на каждом
  узле; `ClassifierTreeSectionClassifier`
  (`src/fe_bot/classifier/section_classifier_adapter.py`) — адаптер
  под интерфейс `DocumentParserOrchestrator`. Результат — новое поле
  `ParsedSection.classifier_result` (не переиспользует bitmap-формат
  `classification_state` — семантика не совместима: произвольная
  глубина/путь vs фиксированные 3 уровня).
- Модель: `qwen2.5:7b`, не `llama3.2` — на живых фрагментах `llama3.2`
  систематически не различал содержание (см. §7 "Использование в
  парсинге документов" в
  [docs/02-system/features/SETUP-13-classifier-library.md](../../02-system/features/SETUP-13-classifier-library.md)
  для деталей эксперимента).
- Per-node `prompt_override` **целиком заменяет** рендер общего
  шаблона (не дополняет) — так первый из открытых вопросов ниже снят.

## Открытые вопросы

- Формат retrieval-фильтра по пути дерева (аналог `TaxonomyFilter` из
  SETUP-12, но path-based, не bitwise) — векторный индекс/retrieval
  пока не знают о `classifier_result`, фильтрация по новому дереву не
  спроектирована.
- Судьба `src/fe_bot/taxonomy/*` (SETUP-12) — код и bitmap-инфра
  остаются нетронутыми (снапшоты со старыми `classification_state`
  по-прежнему читаются), но больше не производятся новым кодом;
  deprecate/удаление — не решено.

## Related

- [ADR-HTC-01 Open taxonomy](ADR-HTC-01-open-taxonomy.md) (superseded)
- [ADR-HTC-02 30-bit bitmap layout](ADR-HTC-02-bitmap-30-layout.md) (superseded)
- [ADR-HTC-10 Metadata-хинты узлов, единая классификация](ADR-HTC-10-classification-hints-single-source.md)
- [docs/02-system/features/SETUP-13-classifier-library.md](../../02-system/features/SETUP-13-classifier-library.md)
- `incoming-docs/raw/Классификатор.md` (исходное дерево)
