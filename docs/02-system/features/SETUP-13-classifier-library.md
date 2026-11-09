# SETUP-13. Библиотека классификаторов

## 1. Назначение фичи

**Краткое название:** SETUP-13. Classifier Library.

**Краткое описание:** Редактируемое дерево классов произвольной
глубины и ширины (не ограничено 3 уровнями/10 классами, в отличие от
SETUP-12 — см. [ADR-HTC-09](../../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)).
У каждого узла с дочерними элементами — промпт (рендер общего
шаблона либо ручной override), с помощью которого маленькая LLM
определяет, в какой из дочерних классов попадает фрагмент текста,
при условии что родительский класс уже определён предыдущим вызовом.

**Какую проблему решает:** первая попытка классификации (SETUP-12,
230 конечных категорий, 3 уровня) не справилась с реальной
предметной таксономией — приложенное дерево (`incoming-docs/raw/Классификатор.md`)
имеет 6 уровней, 906 узлов, до 15 детей на узел. Нужен инструмент,
позволяющий: (а) держать такое дерево в системе, (б) редактировать
его (добавлять/переименовывать/удалять классы, менять промпты) через
UI, а не через код/seed-файл.

**Область охвата этого слайса:** сама библиотека (CRUD дерева и
промптов + UI-вкладка для просмотра/редактирования) и её подключение
к парсингу документов для реальной многоуровневой классификации
фрагментов (см. §7) — реализовано полностью.

**Следующий слайс (дизайн принят, в коде не реализован):** дерево
становится единственным источником классификации секции для всего
Setup-пайплайна. Узлы получают metadata-хинты (`doc_type` и
онтологические поля), результат классификации отдаёт разрешённые по
пути хинты, и шаг 4 (SETUP-05) выводит из них metadata карточки без
повторной классификации LLM — см. §8 и
[ADR-HTC-10](../../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md).

## 2. Пользовательский сценарий

1. Пользователь открывает новый шаг мастера «Классификаторы».
2. Видит дерево классов (изначально — импортированное из
   `Классификатор.md`, 906 узлов).
3. Разворачивает узел, видит его дочерние классы и rendered-промпт
   для перехода на следующий уровень.
4. Может отредактировать промпт узла (override общего шаблона),
   переименовать узел, добавить новый дочерний класс, удалить класс.
5. Изменения сохраняются немедленно (без отдельного review-этапа —
   это конфигурационный ресурс, не RAG-контент).
6. *(целевое поведение, §8)* Для узла задаёт metadata-хинты: тип
   карточки и онтологические поля, в которые превращаются секции этой
   ветки. Видит значения, унаследованные от предков, и узел-источник
   каждого из них; хинт, заданный на дочернем узле, перекрывает
   унаследованный.

## 3. Связанные требования

- Замещает предметную модель SETUP-12 (см. [ADR-HTC-09](../../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)).
  SETUP-12 инфраструктура (`schemas/taxonomy/`, `src/fe_bot/taxonomy/`)
  не удалена, но переключение произошло: `FE_BOT_TAXONOMY_MODE=llm`
  теперь строит `ClassifierTreeSectionClassifier` (SETUP-13), а не
  legacy `HierarchicalSectionClassifier` (SETUP-12).
- Источник начального дерева: `incoming-docs/raw/Классификатор.md`.
- Классификация секции выполняется **один раз** (здесь, на шаге 3); шаг 4
  не переклассифицирует, а берёт `doc_type` и онтологические поля из
  хинтов узлов ([ADR-HTC-10](../../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)).

## 4. Связанные контракты

Реализовано:

- `ClassifierNode` (`schemas/classifier/node.py`): `node_id`,
  `parent_id`, `level`, `name`, `description`, `children_ids`,
  `prompt_override`, `is_leaf`.
- `ClassifierTree` (`schemas/classifier/tree.py`): snapshot всего
  дерева (`tree_id`, `version`, `nodes: dict[node_id, ClassifierNode]`,
  `root_ids`).
- `FragmentClassificationResult` / `ClassifierPathStep`
  (`schemas/classifier/classification_result.py`): `tree_id`, `path`
  (шаги с `node_id`, `name`, `confidence`, `reason`), `reached_leaf`;
  вычисляемые `leaf_node_id`, `path_names`, `overall_confidence`
  (минимум по пути).

Целевые дополнения ([ADR-HTC-10](../../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md), §8 ниже; в коде отсутствуют):

- `ClassifierNode.metadata_hints: ClassifierMetadataHints | None` —
  блок хинтов узла.
- `ClassifierMetadataHints`: `doc_type_hint`, `domain_hint`,
  `task_type_hint`, `data_source_hint`, `entity_type_hint`,
  `phase_hint`, `agent_targets_hint`, `retrieval_purpose_hint` (все
  опциональны).
- `FragmentClassificationResult.resolved_hints: ResolvedMetadataHints`
  — итоговые хинты по пути плюс `sources` (поле → `node_id` узла-источника).

## 5. Связанные сервисы

- `ClassifierTreeRepository` (in-memory, dev-snapshot — паттерн как у
  остальных repo проекта).
- `ClassifierTreeService` — CRUD над деревом + рендер промпта узла.
  *Целевое (§8):* `resolve_hints(path)` — чистая детерминированная
  функция слияния хинтов по пути; валидация хинтов по онтологии при
  сохранении узла.
- `ClassifierPromptRenderer` — общий текстовый шаблон
  (`prompts/classification/classify_node.txt`), параметризован
  именем/описанием узла + списком детей. `{fragment_section}`
  (реальный текст фрагмента) подставляется отдельно — только при
  настоящем вызове классификации, не при редактировании промпта в UI.
- `FragmentClassifier` (`src/fe_bot/classifier/fragment_classifier.py`)
  — многоуровневый обход дерева: на каждом узле рендерит промпт с
  реальным `fragment_text`, спрашивает LLM, спускается по выбранному
  ребёнку; останавливается на листе / `null` / confidence ниже порога
  / guard от "галлюцинированного" id (в т.ч. когда модель путает
  нумерацию списка с самим id и отвечает числом).
- `ClassifierTreeSectionClassifier`
  (`src/fe_bot/classifier/section_classifier_adapter.py`) — адаптер
  `FragmentClassifier` под интерфейс `SectionClassifier.apply_to_sections`,
  которым пользуется `DocumentParserOrchestrator`; пишет результат в
  `ParsedSection.classifier_result`
  (`FragmentClassificationResult` — путь узлов + confidence/reason на
  каждом уровне, `schemas/classifier/classification_result.py`).
- `ClassifierDescriptionGenerator`
  (`src/fe_bot/classifier/description_generator.py`) — черновик
  описания узла через LLM (для непонятных без контекста имён классов,
  напр. аббревиатур вроде "DNN"); возвращается на review, не
  сохраняется автоматически.
- API: `src/fe_bot/api/setup/classifier_router.py`. *Целевое (§8):*
  `PATCH` узла принимает `metadata_hints`; ответ по узлу содержит
  разрешённые (унаследованные) хинты и узлы-источники.
- UI: шаг мастера «Библиотека классификаторов»,
  `frontend/src/components/Wizard/steps/ClassifierLibraryStep.tsx`;
  результат классификации в парсинге — колонка «taxonomy» и вкладка
  «Классификация» в `ParsingStep.tsx`/`SectionDetailDrawer.tsx`.
  *Целевое (§8):* панель узла (`ClassifierNodePanel.tsx`) редактирует
  хинты рядом с `prompt_override`; вкладка «Классификация» показывает
  `resolved_hints` секции.

## 6. Критерии приёмки

- Импорт `Классификатор.md` создаёт дерево с корректной иерархией
  (parent/children консистентны, число узлов на каждом уровне
  соответствует документу: 12 → 64 → 336 → 345 → 122 → 27).
- Для любого узла с детьми `render_prompt(node)` возвращает непустой
  промпт, включающий имя узла и полный список дочерних классов.
- CRUD API: создание/переименование/удаление узла, редактирование
  `prompt_override` — покрыты unit/component-тестами.
- UI-вкладка: разворачиваемое дерево + панель редактирования
  выбранного узла (имя, промпт, список детей, добавить/удалить
  ребёнка).
- Тесты: `tests/unit/test_classifier_tree_import.py`,
  `tests/component/classifier/test_classifier_tree_service.py`.
- `FragmentClassifier` корректно спускается по нескольким уровням до
  листа, останавливается на `null`/low-confidence/guard, разрешает
  numeric-index ответ модели в id по списку детей. Тесты:
  `tests/unit/test_fragment_classifier.py`.
- `ClassifierTreeSectionClassifier.apply_to_sections` заполняет
  `classifier_result`, derive'ит `confidence`/`section_status`.
  Тесты: `tests/component/classifier/test_section_classifier_adapter.py`.
- `DocumentParserOrchestrator` не падает 500-й при сбое классификатора
  (`LLMUnavailableError`/`InvalidLLMOutputError`) — документ помечается
  `FAILED` с `ParseErrorCode.CLASSIFICATION_FAILED`, уже
  классифицированные секции остаются сохранёнными для resume.

Критерии приёмки для хинтов (§8; реализация и тесты — планируются, в
коде и в `tests/` их пока нет):

- **AC-H1.** Узел принимает `metadata_hints`; при `None` или полях `None`
  узел хинтов не задаёт и наследует предков.
- **AC-H2.** `resolve_hints(path)` сливает хинты от корня пути к
  последнему шагу: по каждому полю побеждает самый глубокий узел, у
  которого поле не `None`; список заменяет унаследованный целиком, пустой
  список — тоже значение; для каждого непустого поля `sources` указывает
  `node_id` узла-источника.
- **AC-H3.** `resolve_hints` детерминирован и не обращается к LLM:
  одинаковые `path` и версия дерева дают одинаковый результат.
- **AC-H4.** `FragmentClassifier` заполняет `resolved_hints` по пути,
  на котором остановилась классификация (лист, `null`, низкая
  уверенность, guard); при пустом пути `resolved_hints` пуст.
- **AC-H5.** Сохранение узла отклоняет хинт с неизвестным значением:
  `doc_type_hint` вне `DocType`; значение `domain_hint`, `task_type_hint`,
  `data_source_hint`, `entity_type_hint`, `phase_hint`,
  `agent_targets_hint` вне `ontology_v1.yaml`; `retrieval_purpose_hint`
  вне закрытого множества из [chunk-schema.md](../../06-rag/chunk-schema.md).
  Синонимы не принимаются — только канонические значения.
- **AC-H6.** API и UI показывают для узла разрешённые хинты и узел-
  источник каждого значения; правка хинта сохраняется немедленно (как
  остальные правки дерева) и меняет `version` дерева. Это новое
  требование: сейчас `ClassifierTreeService` копирует `tree.version` при
  правках и не меняет его (по умолчанию `1.0.0`), а без смены версии
  `classifier_tree_version` в карточке ничего не различает.
- **AC-H7.** Покрытие: отчёт по дереву показывает долю листьев без
  разрешённого `doc_type_hint` — это доля секций, которые шаг 4 вернёт с
  `DOC_TYPE_HINT_MISSING`.

## 7. Использование в парсинге документов

При `FE_BOT_TAXONOMY_MODE=llm` (см. `Makefile` — `make run-api`
включает этот режим по умолчанию) каждая секция, извлечённая
`DocumentParserOrchestrator`, классифицируется по активному дереву
классификаторов через `ClassifierTreeSectionClassifier` →
`FragmentClassifier`. Результат — `ParsedSection.classifier_result`
— виден в UI (вкладка «Парсинг документов» → колонка «taxonomy» /
детальная панель секции → вкладка «Классификация»). В целевом дизайне
вместе с путём результат несёт и разрешённые metadata-хинты (§8), из
которых шаг 4 выводит `doc_type` и онтологические поля карточки.
Сейчас ни один шаг после парсинга `classifier_result` не читает.

**Выбор модели.** Изначально использовался `llama3.2` (3.2B) — тот
же, что и для остальных узких LLM-задач проекта. На живых тестовых
фрагментах (включая заведомо нерелевантные, напр. кулинарный рецепт)
модель систематически возвращала один и тот же класс независимо от
содержания — вплоть до противоречия между `reason` и выбранным `id`
в одном и том же ответе, что указывает на пост-хок рационализацию, а
не реальное сопоставление смысла. Правка промпта (reason → confidence
→ selected_child_id вместо id → confidence → reason, чтобы
рассуждение предшествовало решению; повтор списка id
непосредственно перед JSON; few-shot примеры из другого домена) дала
частичное улучшение, но не устранила проблему на тривиальных случаях.
`qwen2.5:7b` на тех же промптах и фрагментах классифицирует корректно
(включая верный `null` для нерелевантного текста и содержательно
верный многоуровневый путь для тематических фрагментов) — сейчас это
`_DEFAULT_MODEL` в `FragmentClassifier`. Компромисс: заметно медленнее
`llama3.2` (~2–3× latency на уровень дерева), поэтому классификация
всего документа в этом режиме ощутимо дольше, чем `rule_based`.

## 8. Metadata-хинты узлов

*Целевой дизайн по [ADR-HTC-10](../../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md). В коде пока нет — см. [TD-HTC-004](../../tech-debt/TD-HTC-004-duplicate-classification-in-card-generation.md).*

### 8.1. Зачем

Классификация по дереву — единственное место, где система понимает смысл
фрагмента относительно предметной таксономии. Чтобы шаг 4 (SETUP-05) не
классифицировал секцию заново (ни `DocTypeDetector`, ни LLM-промптом),
узел дерева сам хранит, во что превращается относящаяся к нему секция:
тип карточки и онтологические поля. Идея `doc_type_hint` перенесена из
seed SETUP-12 ([§7](SETUP-12-llm-taxonomy-classification.md)), но
распространена на все онтологические поля и на произвольную глубину
дерева.

### 8.2. Поля блока `metadata_hints`

| Поле | Тип | Куда попадает | Допустимые значения |
| --- | --- | --- | --- |
| `doc_type_hint` | `DocType \| None` | `doc_type` карточки | `DocType` (`schemas/rag/ontology.py`); генерацией в MVP поддержаны 7 типов, см. [SETUP-05 §3](SETUP-05-rag-cards-generation.md) |
| `domain_hint` | `list[str] \| None` | `domain` | `ontology_v1.yaml → domain` |
| `task_type_hint` | `list[str] \| None` | `task_type` | `ontology_v1.yaml → task_type` |
| `data_source_hint` | `list[str] \| None` | `data_source` | `ontology_v1.yaml → data_source` |
| `entity_type_hint` | `list[str] \| None` | `entity_type` | `ontology_v1.yaml → entity_type` |
| `phase_hint` | `list[str] \| None` | `phase` карточки, `phase` чанков | `ontology_v1.yaml → phase` |
| `agent_targets_hint` | `list[str] \| None` | `agent_targets` | `ontology_v1.yaml → agent_targets` |
| `retrieval_purpose_hint` | `list[str] \| None` | `retrieval_purpose` чанков (шаг 7) | закрытое множество из [chunk-schema.md](../../06-rag/chunk-schema.md#retrieval_purpose) |

`None` у поля означает «хинт не задан, наследуется от предка». Любой
список, включая пустой, — «задано» и заменяет унаследованное значение
целиком (объединения списков нет).

### 8.3. Наследование и слияние

Хинты не нужно задавать на каждом из 906 узлов. Их задают на верхних
уровнях, листья наследуют. `resolve_hints(path)` обходит путь классификации
от корня к последнему шагу и для каждого поля берёт значение **самого
глубокого** узла, у которого оно не `None`. Узел-источник записывается в
`sources`.

Иллюстративный пример (значения не взяты из реального дерева):

| Узел пути | Заданные хинты |
| --- | --- |
| Задача | `doc_type_hint=task_card`, `phase_hint=[task_discovery]`, `agent_targets_hint=[TaskDiscoveryAgent]` |
| Задача → Назначение | — |
| Задача → Назначение → Область применения | — |
| Задача → Назначение → Область применения → Военное наблюдение | `domain_hint=[naval]`, `phase_hint=[task_discovery, domain_context]` |

Результат для этого пути:

| Поле | Значение | Источник |
| --- | --- | --- |
| `doc_type_hint` | `task_card` | Задача |
| `domain_hint` | `[naval]` | Военное наблюдение |
| `phase_hint` | `[task_discovery, domain_context]` | Военное наблюдение (заменило, не дополнило) |
| `agent_targets_hint` | `[TaskDiscoveryAgent]` | Задача |
| остальные | не заданы | — |

Если классификация остановилась на промежуточном узле (низкая
уверенность, `null`, guard), слияние идёт до последнего принятого шага
пути. Если путь пуст — хинтов нет.

### 8.4. Результат шага 3: `resolved_hints`

`FragmentClassificationResult.resolved_hints` (`ResolvedMetadataHints`)
содержит итоговые значения восьми полей и `sources`. Это **снимок на
момент классификации**: он нужен UI парсинга и аудиту. Для генерации карточек
SETUP-05 пересчитывает хинты по сохранённому `path` и текущей версии
дерева (`resolve_hints` дёшев и не использует LLM), поэтому исправление
хинта в UI не требует повторного парсинга и повторной классификации.

### 8.5. Что делается с хинтами дальше

| Шаг | Потребитель | Использование |
| --- | --- | --- |
| 4. Генерация карточек ([SETUP-05](SETUP-05-rag-cards-generation.md)) | `ClassificationMetadataResolver` | `doc_type` и онтологические поля карточки; контекст для промпта LLM |
| 5–6. Review и валидация ([SETUP-06](SETUP-06-rag-card-review.md), [SETUP-07](SETUP-07-metadata-validation.md)) | Ревьюер, валидатор | Видят путь и источник значений; значения проверяются по онтологии независимо от происхождения |
| 7. Чанкинг ([SETUP-08](SETUP-08-chunking.md)) | Chunking | `phase` и `retrieval_purpose` чанка из metadata карточки |
| Runtime | Retrieval ([retrieval-политики](../../06-rag/retrieval-policies.md)) | Фильтры по `doc_type`, `phase`, `agent_targets` и другим полям |

### 8.6. Узел без хинта

Если по всему пути нет `doc_type_hint`, шаг 4 не угадывает тип карточки.
Секция получает отказ `DOC_TYPE_HINT_MISSING` с причиной «taxonomy node has
no doc_type_hint» и путём классификации; выход — задать хинт на узле и
повторить генерацию (см. [SETUP-05 §7.3, N11](SETUP-05-rag-cards-generation.md)).
Отсутствие остальных хинтов не блокирует карточку, но при нехватке
обязательных `domain` и `phase` она получает `metadata_incomplete`.
Реальное дерево построено по рубрикам описания АСУ, а не по типам
карточек, поэтому не у каждой ветки есть очевидный `doc_type`; охват
хинтами измеряется (AC-H7).

### 8.7. Тесты (планируются)

- `tests/unit/test_classifier_metadata_hints.py` — схема блока, валидация значений (AC-H1, AC-H5).
- `tests/unit/test_classifier_resolve_hints.py` — слияние, перекрытие, пустой список, пустой путь, `sources`, детерминизм (AC-H2..H4).
- `tests/component/classifier/test_classifier_hints_api.py` — `PATCH` с хинтами, отказ при неизвестном значении, смена версии дерева (AC-H5, AC-H6).
- `tests/component/classifier/test_hints_coverage.py` — доля листьев без `doc_type_hint` (AC-H7).
