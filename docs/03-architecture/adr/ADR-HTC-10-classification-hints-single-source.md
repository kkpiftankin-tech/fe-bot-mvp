# ADR-HTC-10. Единственная классификация секции: metadata-хинты узлов дерева вместо повторной классификации в шаге 4

## Status

Accepted (дизайн). Реализация в коде не начата — текущее состояние описано в разделе «Текущее состояние кода» и в [TD-HTC-004](../../tech-debt/TD-HTC-004-duplicate-classification-in-card-generation.md).

Дополняет [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md): снимает его «последующий этап» — как результат классификации по дереву используется дальше по пайплайну.

## Context

На вопрос «что это за фрагмент и какая у него metadata» в Setup-пайплайне отвечают **три независимых механизма**, не знающие друг о друге:

| # | Механизм | Где | Что решает |
| --- | --- | --- | --- |
| 1 | Классификатор по дереву ([SETUP-13](../../02-system/features/SETUP-13-classifier-library.md)) | Шаг 3, `FragmentClassifier` → `ParsedSection.classifier_result` | Путь по предметному дереву (906 узлов, 6 уровней) с confidence на каждом уровне |
| 2 | Rule-based `DocTypeDetector` | Шаг 4, `section_type → doc_type` | `doc_type` карточки |
| 3 | LLM-промпт генерации карточки | Шаг 4, `prompts/rag_card/*.txt` (и legacy `card_generator/service.py::_build_prompt`) | Заново, по сырому тексту: `domain`, `task_type`, `data_source`, `entity_type`, `phase`, `agent_targets` |

Это дублирование, а не разделение ответственности:

- Единственный механизм, который понимает смысл фрагмента относительно предметной таксономии (№1), шагом 4 **игнорируется**: код генерации карточки не читает `classifier_result`.
- №2 зависит от `ParsedSection.section_type`, а `ClassifierTreeSectionClassifier` для любой секции записывает `section_type = OTHER` (`UNKNOWN`, если ни один класс верхнего уровня не подошёл), потому что дерево SETUP-13 не выводит legacy-enum. Поэтому в режиме `FE_BOT_TAXONOMY_MODE=llm` у `DocTypeDetector` нет сигнала (кроме случайного слова-маркера вроде «определение» в заголовке) и секция падает с `INVALID_DOC_TYPE` / `No doc_type for section_type=other`. Это корневая причина, а не дефект маппинга.
- №3 заставляет маленькую LLM угадывать онтологические поля по тексту второй раз, независимо от №1; ответы расходятся.
- [metadata-schema.md §6.4](../../06-rag/metadata-schema.md) формулирует правильный принцип — детерминированное извлечение приоритетнее LLM, — но реализация ему противоречит: LLM шага 4 переопределяет то, что шаг 3 уже вычислил.

Механизм SETUP-12 (bitmap-таксономия, `doc_type_hint` на узле L0) решал эту задачу правильно по форме — узел знал, во что превращается, — но замещён SETUP-13 и не применим к дереву в 906 узлов ([ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md)). Идею `doc_type_hint` нужно перенести в SETUP-13.

## Decision

1. **Смысловая классификация фрагмента выполняется один раз — на шаге 3** (`FragmentClassifier`, SETUP-13). Шаг 4 и далее её не повторяют и не переопределяют.
2. **Узел дерева знает, во что он превращается.** `ClassifierNode` получает опциональный блок `metadata_hints` (тип `ClassifierMetadataHints`):

   | Поле | Тип | Для чего |
   | --- | --- | --- |
   | `doc_type_hint` | `DocType \| None` | `doc_type` карточки |
   | `domain_hint` | `list[str] \| None` | `domain` |
   | `task_type_hint` | `list[str] \| None` | `task_type` |
   | `data_source_hint` | `list[str] \| None` | `data_source` |
   | `entity_type_hint` | `list[str] \| None` | `entity_type` |
   | `phase_hint` | `list[str] \| None` | `phase` карточки и чанков |
   | `agent_targets_hint` | `list[str] \| None` | `agent_targets` |
   | `retrieval_purpose_hint` | `list[str] \| None` | `retrieval_purpose` чанков (шаг 7) |

3. **Хинты наследуются вниз по дереву.** Их не задают на каждом из 906 узлов — задают на верхних уровнях (например, на корневой рубрике «Задача»), листья наследуют. Правило слияния от корня к самому глубокому классифицированному узлу: **более специфичный узел перекрывает общий, по каждому полю отдельно**; `None` — «не задано, наследуется», любой список (в том числе пустой) — «задано, заменяет унаследованное целиком» (объединения списков нет).
4. **Результат шага 3 отдаёт разрешённые хинты.** `FragmentClassificationResult` получает поле `resolved_hints` (тип `ResolvedMetadataHints`): итоговые значения восьми полей плюс `sources` — карта «поле → `node_id` узла, давшего значение». Слияние выполняет одна чистая функция `ClassifierTreeService.resolve_hints(path)`.
5. **Шаг 4 выводит `doc_type` и онтологические поля детерминированно** — новым компонентом `ClassificationMetadataResolver` (SETUP-05) из `resolved_hints`, без LLM. Он **заменяет `DocTypeDetector`**; `MetadataExtractor` остаётся, потому что извлекает не классификацию, а содержательные кандидаты (`title`, `retrieval_tags`, `required_input_fields`, `output_fields`, `feature_tables`).
6. **LLM шага 4 больше не классифицирует.** Промпт получает классификацию как контекст («секция классифицирована как `Задача → Назначение → Область применения → Военное наблюдение`, `doc_type=task_card`, `domain=[naval]` …»; значения иллюстративны). LLM производит только содержимое: `title`, `body_markdown`, doc_type-специфичные поля (`task_inputs`, `metrics` и т. п.), уточняющие `retrieval_tags` и **content-confidence** — уверенность в извлечённом содержании, а не в классификации. Онтологические поля в ответе LLM, если они всё же появились, отбрасываются.
7. **Нет `doc_type_hint` по всему пути — это явный отказ, а не молчаливый.** Секция не отправляется в LLM (без `doc_type` нельзя выбрать шаблон промпта), карточка не создаётся; job-секция получает код `DOC_TYPE_HINT_MISSING` с читаемой причиной «taxonomy node has no doc_type_hint» и путём классификации, и показывается пользователю как «требует настройки дерева». Выход: задать хинт на узле (SETUP-13) и повторить генерацию этой секции. Если `doc_type` определён, но не хватает обязательных `domain` / `phase` — карточка создаётся со статусом `metadata_incomplete` и причиной вида «taxonomy node has no domain_hint».
8. **Хинты редактируются там же, где `prompt_override`** — в UI библиотеки классификаторов (шаг 11 мастера). Значения валидируются при сохранении узла по онтологии (`ontology_v1.yaml`, `DocType`, закрытое множество `retrieval_purpose` из [chunk-schema.md](../../06-rag/chunk-schema.md)).
9. **Хинты — источник `phase` и `retrieval_purpose` для чанков.** Эти поля чанка шаг 7 берёт из metadata карточки (которая получена из хинтов), а не из отдельной эвристики. `slot` и `canonical_feature` хинтами не покрываются (открытый вопрос 2).

Распределение ответственности после решения:

| Функция | Где живёт | Где не дублируется |
| --- | --- | --- |
| Разбиение на секции, иерархия, offsets | Шаг 3, парсер | — |
| Смысловая классификация (путь + confidence) | Шаг 3, SETUP-13 `FragmentClassifier` | Шаг 4 не классифицирует заново |
| `doc_type` и онтологические поля из классификации | Граница 3→4, детерминированно, через `resolved_hints` | В промпте LLM их нет |
| Синтез содержимого карточки | Шаг 4, LLM | — |
| Структурная и онтологическая валидация | Шаг 4 precheck и шаг 6 (SETUP-07) | Не в шаге 3 |
| Человеческая проверка смысла | Шаг 5 (SETUP-06) | — |
| Чанкинг, наследование metadata, `retrieval_purpose` / `phase` чанка | Шаг 7 (SETUP-08) | — |

## Consequences

### Положительные

- Один источник истины о смысле фрагмента; корневая причина `INVALID_DOC_TYPE` в режиме `llm` устраняется тем, что конкурирующий `DocTypeDetector` перестаёт участвовать в выводе, а не обходным путём совместимости.
- Принцип «детерминированное приоритетнее LLM» ([metadata-schema.md §6.4](../../06-rag/metadata-schema.md)) выполняется структурно.
- Подробная онтологическая metadata идёт из проверяемого, редактируемого дерева, а не из догадки маленькой LLM по сырому тексту — это даёт Runtime релевантный, а не шумный контекст.
- Сквозная трассировка: узел дерева → `resolved_hints.sources` → metadata карточки → metadata чанка → retrieval-фильтр ([retrieval-policies.md](../../06-rag/retrieval-policies.md)).
- Системная ошибка настройки (у ветки нет хинта) становится видимой одному администратору в одном месте, а не россыпью `INVALID_DOC_TYPE` по секциям.
- Задача LLM сужается до того, что она делает надёжно (формулировка текста), что соответствует правилу «маленькие LLM выполняют узкие задачи».

### Отрицательные и риски

- **Качество результата ограничено качеством хинтов.** Ошибка хинта на верхнем узле тиражируется на всё поддерево. Смягчение: наследование можно перекрыть на любом уровне; `resolved_hints.sources` показывает, какой узел дал значение; SETUP-06 проверяет смысл.
- **Предметное дерево и тип карточки — разные оси.** Дерево `seed/classifier/asu_v1.txt` описывает систему по рубрикам (12 корневых: «Задача», «Требования», «Функциональность», «Архитектура», «Данные», «Аналитика», «Сценарий», «Реализация», «Проверка», «Эксплуатация», «Пример», «Справка»), а не по типам карточек. Кандидаты на соответствие 7 MVP-типам видны лишь у части рубрик («Задача» → `task_card`, «Данные» → `schema_card`, «Аналитика» → `analytics_card`, «Проверка» → `validation_rule_card`, «Справка» → `field_definition_card`; это предположение для предметного эксперта, а не решение). У «Требований», «Функциональности», «Архитектуры», «Сценария», «Реализации», «Эксплуатации» и «Примера» очевидного типа нет. Для таких веток хинт не задаётся, и секции явно уходят в «требует настройки дерева» (п. 7) — это сознательный выбор вместо угадывания. Следствие для MVP: доля секций, по которым карточки не создаются, определяется покрытием дерева хинтами, и это надо измерять (см. SETUP-13, критерий приёмки о покрытии).
- **Правка хинта меняет результат без перепарсинга.** Чтобы исправление хинта работало без повторной (дорогой, ~2–3× медленнее `llama3.2` на уровень) классификации, шаг 4 пересчитывает `resolved_hints` по сохранённому `classifier_result.path` и **текущей** версии дерева; в карточку записывается `classifier_tree_version`. Снимок в `classifier_result.resolved_hints` остаётся для отображения в UI парсинга.
- **Режим `rule_based`** (`FE_BOT_TAXONOMY_MODE` ≠ `llm`) не создаёт `classifier_result`, хинтов нет, и секции получат `DOC_TYPE_HINT_MISSING`. См. открытый вопрос 1.
- Типы `doc_type` вне 7 MVP-типов генерации (`glossary_term`, `domain_profile` и др.) допустимы как значение хинта (они есть в `DocType`), но шаг 4 откажет по той же ветке п. 7 с причиной «doc_type вне поддерживаемых генерацией». В seed SETUP-12 значения `domain_profile_card`, `process_card`, `reference_card` не совпадают ни с одним значением `DocType`; при переносе идеи они не копируются.
- Шаблоны промптов `prompts/rag_card/*.txt` и контракт `RAGCardDraft` придётся менять (убрать онтологические поля из ожидаемого ответа LLM).

## Текущее состояние кода (на 2026-11-06)

Этот ADR описывает целевой дизайн. В коде сейчас:

- `ClassifierNode` (`schemas/classifier/node.py`) несёт только `name`, `description`, `prompt_override`; `FragmentClassificationResult` — только путь и confidence.
- `ClassifierTree.version` — строка (`1.0.0` по умолчанию), которую правки узлов не меняют; для `classifier_tree_version` в карточке версия должна меняться при каждой правке дерева.
- `RAGCardGenerationOrchestrator._process_section` вызывает `DocTypeDetector.detect(section)` по `section_type`; `classifier_result` не читается.
- Шаблоны `prompts/rag_card/*.txt` просят LLM вернуть `domain`, `task_type`, `data_source`, `entity_type`, `phase`, `agent_targets` из списков онтологии; `RAGCardDraft` (`rag_card_generation/precheck.py`) требует `doc_type` от LLM.
- Тот же дефект, в более грубой форме, в legacy-генераторе `RAGCardGenerator` (`src/fe_bot/setup/card_generator/service.py`, `_build_prompt`): LLM просят выбрать `doc_type` из 13 значений, `phase` и `agent_targets`, а `section_type` подаётся как «эвристика». Им пользуется только внутренний monolith-`SetupPipeline` (`setup/pipeline.py`, помечен LEGACY и убран из шагов мастера); гранулярный флоу мастера идёт через `RAGCardGenerationOrchestrator`.
- `ConfidenceCalculator` учитывает классификацию только через legacy `ClassificationState` (SETUP-12).

## Открытые вопросы

1. **Судьба `rule_based`-режима и `DocTypeDetector`.** Рекомендация: оставить `DocTypeDetector` только как переходный fallback при `classifier_result is None`, пометить deprecated и удалить вместе с `rule_based`-режимом; при наличии `classifier_result` он не вызывается никогда.
2. **`slot` и `canonical_feature` чанка** не покрываются хинтами из этого решения — их нечем вывести из узла дерева. Источник определяется при проектировании чанкинга ([SETUP-08](../../02-system/features/SETUP-08-chunking.md)).
3. **Retrieval-фильтр по пути дерева** (открытый вопрос ADR-HTC-09) остаётся открытым; хинты закрывают фильтры по онтологическим полям, но не по самому пути.
4. **Как из списка `phase` карточки выбирается одно значение `phase` чанка** (`chunk-schema.md` описывает скаляр) — уточняется вместе с вопросом 2.

## Related

- [ADR-HTC-09](ADR-HTC-09-generic-tree-classifier-library.md) — библиотека классификаторов
- [SETUP-13](../../02-system/features/SETUP-13-classifier-library.md) — хинты узлов, `resolved_hints`
- [SETUP-04](../../02-system/features/SETUP-04-document-parsing.md), [SETUP-05](../../02-system/features/SETUP-05-rag-cards-generation.md), [SETUP-07](../../02-system/features/SETUP-07-metadata-validation.md), [SETUP-08](../../02-system/features/SETUP-08-chunking.md)
- [metadata-schema.md](../../06-rag/metadata-schema.md), [chunk-schema.md](../../06-rag/chunk-schema.md), [card-lifecycle.md](../../06-rag/card-lifecycle.md)
- [TD-HTC-004](../../tech-debt/TD-HTC-004-duplicate-classification-in-card-generation.md)
