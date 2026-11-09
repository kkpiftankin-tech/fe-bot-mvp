# Metadata-схема RAG-карточки

Все RAG-карточки хранятся в YAML (front matter) + Markdown (тело). Эта страница нормативна: каждый ключ обязателен или явно опционален.

---

## SETUP-05 Metadata Schema v1

Раздел описывает **обязательные и опциональные поля** RAG-карточки (YAML front matter), которые RAG Card Generator (SETUP-05) обязан сгенерировать, и которые SETUP-07 Metadata Validation Service проверит перед переходом карточки в следующий этап пайплайна.

---

## 1. Назначение

Metadata-схема v1 задаёт единый контракт для YAML front matter RAG-карточки. Она обеспечивает:

- машинно-читаемую фильтрацию при retrieval (по `doc_type`, `phase`, `agent_targets`, `domain`, `task_type`, `data_source`, `entity_type`);
- трассируемость от source document до chunk/embedding/Evidence Pack;
- автоматическую классификацию карточек по применимости к конкретному агенту и фазе workflow;
- возможность governance — human review, валидация, deprecation — на основе типизированных полей.

Схема используется в:

- `RAGCardGenerationOrchestrator` (SETUP-05) — генерирует front matter;
- `MetadataExtractor` + `OntologyMapper` — извлекают и нормализуют значения;
- `CardValidationPrecheck` (SETUP-05) и `SETUP-07 Metadata Validation Service` — проверяют соответствие;
- `RAGRetrievalAgent` — фильтрует карточки при retrieval.

---

## 2. Версионирование

Текущая версия схемы: **`rag_metadata_v1`**.

Версия хранится в поле `metadata_schema_version` каждой карточки и в `RAGCardMetadataDTO.metadata_schema_version`. Это позволяет SETUP-07 применять правила валидации, соответствующие той версии схемы, с которой карточка была сгенерирована.

Правила bump версии:

- **Добавление опционального поля** — backward-compatible. Новая версия схемы не обязательна; старые карточки остаются валидными.
- **Изменение обязательного поля** (переименование, смена типа, удаление) — требует bump до `rag_metadata_v2`.
- **Добавление значения в enum ontology** — backward-compatible; выполняется через bump `ontology_v1` → `ontology_v2`.

При bump `rag_metadata_v1` → `rag_metadata_v2`:

1. Создать новую `metadata_schema_version = "rag_metadata_v2"` в конфигурации.
2. Старые карточки (`metadata_schema_version = "rag_metadata_v1"`) остаются без изменений — не ломаются, не мигрируются автоматически.
3. Новые карточки генерируются с `rag_metadata_v2`.
4. SETUP-07 Validation Service использует версию схемы, указанную в поле `metadata_schema_version` карточки.
5. При deprecation `rag_metadata_v1` — все карточки с v1 получают статус `deprecated` или подлежат ручной миграции через отдельный migration job.

---

## 3. Общие обязательные поля (для всех `doc_type`)

Следующие поля обязаны присутствовать в YAML front matter каждой RAG-карточки независимо от её типа. Отсутствие любого из них — blocking error в `CardValidationPrecheck`: карточка не переходит в статус `generated`.

| Поле | Тип | Примечания |
| --- | --- | --- |
| `doc_id` | string | Уникален в пределах `(setup_job_id, card_version)`. Паттерн: `{doc_type_short}.{slug}.v{N}`, например `analytics.sensor_analytics_T.v1`. Генерируется детерминированно через `DocIdGenerator`. |
| `doc_type` | enum | Один из 7 MVP-типов (`schema_card`, `task_card`, `analytics_card`, `field_definition_card`, `feature_pattern_card`, `validation_rule_card`, `question_template_card`). Значение нормализуется `OntologyMapper`. |
| `title` | string | Человекочитаемое название карточки. Непустое. |
| `version` | string | Семантическая версия карточки, например `"1.0"`. Монотонно возрастает при `regenerate`. |
| `status` | enum | Один из 10 допустимых статусов (`draft`, `generated`, `generation_failed`, `metadata_incomplete`, `body_empty`, `low_confidence`, `review_required`, `ready_for_metadata_validation`, `rejected`, `deprecated`). |
| `source_files` | list[string] | Непустой список. Имена (filename) исходных документов, из которых построена карточка. Берётся из Source Registry. |
| `source_sections` | list[string] | Непустой список. `section_id`-ы `ParsedSectionDTO`, послуживших источниками. |
| `domain` | list[string] | Один или несколько canonical values из `ontology_v1.yaml → domain`. Валидируется `OntologyMapper`. |
| `phase` | list[string] | Один или несколько canonical values из `ontology_v1.yaml → phase`. |
| `retrieval_tags` | list[string] | 3–10 ключевых слов/фраз для reranking при retrieval. Карточки с пустым списком получают warning `RETRIEVAL_TAGS_EMPTY`. |
| `metadata_schema_version` | string | Всегда `"rag_metadata_v1"` для карточек, сгенерированных SETUP-05 v1. |

---

## 4. Общие опциональные поля

Следующие поля рекомендованы, но не блокируют генерацию при отсутствии. Карточка с более чем 2 warnings по опциональным полям получает статус `review_required`.

| Поле | Тип | Примечания |
| --- | --- | --- |
| `task_type` | list[string] | Canonical values из `ontology_v1.yaml → task_type`. Например `["classification", "ranking"]`. |
| `data_source` | list[string] | Canonical values из `ontology_v1.yaml → data_source`. Например `["radar", "tracks_fused"]`. |
| `entity_type` | list[string] | Canonical values из `ontology_v1.yaml → entity_type`. Например `["sensor", "track"]`. |
| `agent_targets` | list[string] | Canonical values из `ontology_v1.yaml → agent_targets`. Имена Python-классов агентов. Например `["FeatureSynthesisAgent", "FeatureCriticAgent"]`. |
| `required_input_fields` | list[string] | Список полей, которые должны присутствовать в данных. Актуально для `schema_card`, `analytics_card`. |
| `output_fields` | list[string] | Список полей/признаков, которые карточка описывает на выходе. Актуально для `schema_card`, `analytics_card`. |
| `feature_tables` | list[FeatureTable] | Структурированные таблицы признаков. Формат: `{table_id: string, columns: list[string]}`. Актуально для `analytics_card`, `schema_card`. |
| `validation_rules` | list[ValidationRule] | Список правил проверки. Формат: `{rule_id: string, condition: string, severity: string}`. Только для `validation_rule_card`. |
| `compatible_models` | list[string] | Список рекомендованных моделей. Только для `task_card`. |
| `confidence_level` | enum | `high`, `medium`, `low`. Вычисляется `ConfidenceCalculator`. Граничные значения: `high` ≥ 0.85, `medium` 0.6–0.85, `low` < 0.6. |
| `classifier_path` | list[string] | Целевое. Имена узлов пути классификации по дереву SETUP-13, от корневой рубрики до последнего принятого узла. Трассировка происхождения `doc_type` и онтологических полей. Не участвует в retrieval-фильтрах до решения по path-based фильтру ([ADR-HTC-09](../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md), открытый вопрос). |
| `classifier_tree_version` | string | Целевое. `ClassifierTree.version`, по которой вычислены хинты. |
| `owner` | string | Команда или имя ответственного. |
| `last_verified_at` | datetime | Дата последней верификации содержимого карточки. |

---

## 5. Специфичные обязательные поля по типам карточек

Для каждого из 7 MVP `doc_type` приведены дополнительные обязательные поля и рекомендуемая структура Markdown body.

---

### schema_card

Описывает структуру данных, сущности, поля, источники данных.

**Дополнительные обязательные поля:**

- `feature_tables` — список `{table_id, columns}` объектов; минимум 1 таблица.
- `required_input_fields` — list[string]; поля, необходимые для работы схемы.
- `output_fields` — list[string]; поля, которые схема описывает.

**Рекомендуемые опциональные поля:** `entity_type`, `data_source`, `agent_targets`.

**Структура Markdown body (рекомендуемая):**

```markdown
# {title}

## Описание схемы
{краткое описание структуры данных}

## Поля
| Поле | Тип | Описание |
|------|-----|----------|
| ... | ... | ... |

## Источник
{ссылка на source document / section}
```

---

### task_card

Описывает ML-задачу: target, классы, метрики, модели.

**Дополнительные обязательные поля:**

- `task_type` — list[string]; хотя бы один canonical value из ontology.

**Рекомендуемые опциональные поля:** `compatible_models`, `entity_type`, `agent_targets`, `data_source`.

**Структура Markdown body (рекомендуемая):**

```markdown
# {title}

## Описание задачи
{постановка ML-задачи}

## Target
{целевая переменная}

## Классы / значения
{перечень классов или диапазон}

## Метрики качества
{список метрик}

## Рекомендуемые модели
{список}

## Источник
{ссылка на source document / section}
```

---

### analytics_card

Описывает feature-store таблицы, агрегаты, аналитические признаки.

**Дополнительные обязательные поля:**

- `feature_tables` — список `{table_id, columns}` объектов; минимум 1 таблица.
- `output_fields` — list[string]; выходные признаки таблицы.

**Рекомендуемые опциональные поля:** `entity_type`, `data_source`, `agent_targets`, `task_type`.

**Структура Markdown body (рекомендуемая):**

```markdown
# {title}

## Описание аналитической таблицы
{назначение и контекст}

## Признаки
| Признак | Тип | Описание |
|---------|-----|----------|
| ... | ... | ... |

## Агрегации
{описание агрегатов, окна, группировки}

## Источник
{ссылка на source document / section}
```

---

### field_definition_card

Описывает отдельное поле данных: синонимы, единицы измерения, типы, допустимые значения.

**Дополнительные обязательные поля:**

- `required_input_fields` — list[string] с минимум одним значением (само описываемое поле).

**Рекомендуемые опциональные поля:** `entity_type`, `data_source`, `output_fields`, `agent_targets`.

**Структура Markdown body (рекомендуемая):**

```markdown
# {title}

## Описание поля
{семантика поля}

## Синонимы
{список синонимов / альтернативных имён}

## Тип и единицы
{тип данных, единицы измерения}

## Допустимые значения
{диапазон или enum}

## Источник
{ссылка на source document / section}
```

---

### feature_pattern_card

Описывает шаблон (паттерн) формирования признака: формула, входные поля, evidence.

**Дополнительные обязательные поля:**

- `required_input_fields` — list[string]; входные поля для вычисления признака.
- `output_fields` — list[string]; выходные признаки.

**Рекомендуемые опциональные поля:** `task_type`, `entity_type`, `data_source`, `agent_targets`.

**Структура Markdown body (рекомендуемая):**

```markdown
# {title}

## Описание паттерна
{назначение и контекст}

## Формула / Алгоритм
{математическое выражение или псевдокод}

## Входные поля
{список}

## Выходные поля
{список}

## Применение
{в каких задачах и фазах используется}

## Источник
{ссылка на source document / section}
```

---

### validation_rule_card

Описывает правило проверки данных или признаков.

**Дополнительные обязательные поля:**

- `validation_rules` — list[ValidationRule]; минимум 1 правило. Формат каждого: `{rule_id: string, condition: string, severity: "error" | "warning"}`.

**Рекомендуемые опциональные поля:** `required_input_fields`, `entity_type`, `data_source`, `agent_targets`, `task_type`.

**Структура Markdown body (рекомендуемая):**

```markdown
# {title}

## Описание правила
{что проверяется и почему}

## Условие
{формальное условие / предикат}

## Severity
{error | warning}

## Применение
{когда и где применяется}

## Источник
{ссылка на source document / section}
```

---

### question_template_card

Шаблон уточняющего вопроса для пользователя при отсутствующем слоте в диалоге.

**Дополнительные обязательные поля:**

- `required_input_fields` — list[string]; список слотов, для которых задаётся вопрос.

**Рекомендуемые опциональные поля:** `agent_targets`, `task_type`, `phase`, `entity_type`.

**Структура Markdown body (рекомендуемая):**

```markdown
# {title}

## Шаблон вопроса
{текст вопроса с заполнителями}

## Слоты
{список переменных, которые заполняет вопрос}

## Контекст применения
{когда задаётся вопрос, в какой фазе}

## Примеры
{примеры использования}

## Источник
{ссылка на source document / section}
```

---

## 6. Политика валидации

### 6.1. Blocking errors (карточка не сохраняется как `generated`)

Следующие нарушения приводят к статусу `metadata_incomplete` или `generation_failed` и блокируют переход карточки к SETUP-07:

- отсутствие любого из полей §3 (`doc_id`, `doc_type`, `title`, `version`, `status`, `source_files`, `source_sections`, `domain`, `phase`, `retrieval_tags`, `metadata_schema_version`);
- `doc_type` не входит в допустимый enum из `ontology_v1.yaml`;
- `source_files` или `source_sections` — пустые списки;
- `doc_id` конфликтует с существующей карточкой без инкремента версии;
- отсутствие `feature_tables` у `schema_card` или `analytics_card`;
- отсутствие `validation_rules` у `validation_rule_card`;
- значение в `domain`, `phase`, `task_type`, `data_source`, `entity_type`, `agent_targets` — неизвестно ontology и не может быть mapped через синонимы.

### 6.2. Warnings (карточка → `review_required` при более чем 2 warnings)

- `retrieval_tags` — пустой список: `WARNING_RETRIEVAL_TAGS_EMPTY`;
- отсутствуют `task_type`, `data_source`, `entity_type`, `agent_targets` (рекомендованы для большинства типов): `WARNING_OPTIONAL_FIELD_MISSING`;
- `domain` содержит значение `custom`: `WARNING_DOMAIN_CUSTOM` (карточка автоматически получает `review_required`);
- значение в любом ontology-поле неизвестно Ontology Mapper (не может быть mapped): `WARNING_ONTOLOGY_UNKNOWN_TERM`;
- `confidence_level = low`: `WARNING_LOW_CONFIDENCE`.

### 6.3. Правило `domain = custom`

Карточки с `domain = custom` **всегда** получают `status = review_required` вне зависимости от количества других warnings. Это требование BR-20 из §12 SETUP-05.

### 6.4. Приоритеты при конфликте

- Canonical ontology values имеют приоритет над LLM-предложениями.
- Детерминированные источники — metadata-хинты классификации ([SETUP-13 §8](../02-system/features/SETUP-13-classifier-library.md#8-metadata-хинты-узлов)) и `MetadataExtractor` — имеют приоритет над LLM metadata. В целевом дизайне приоритет безусловный: LLM не определяет `doc_type` и онтологические поля (правило «при равном или более высоком confidence» из прежней редакции отменено, [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)).
- Source trace (`source_files`, `source_sections`) берётся из Source Registry, а не из LLM output.

### 6.5. Происхождение значений полей (целевой дизайн)

Каждое поле metadata имеет ровно один основной источник; смысловая классификация выполняется один раз на шаге 3 и дальше не повторяется.

| Поля | Источник | Кто вычисляет | Может ли LLM изменить |
| --- | --- | --- | --- |
| `doc_type` | `doc_type_hint` узла по пути классификации | `ClassificationMetadataResolver` (SETUP-05) | Нет |
| `domain`, `task_type`, `data_source`, `entity_type`, `phase`, `agent_targets` | одноимённые `*_hint` узла по пути классификации | `ClassificationMetadataResolver` | Нет |
| `source_files`, `source_sections` | Source Registry | оркестратор SETUP-05 | Нет |
| `doc_id`, `version`, `status`, `metadata_schema_version` | детерминированные правила | `DocIdGenerator`, оркестратор | Нет |
| `title`, `retrieval_tags` | содержимое секции | `MetadataExtractor` даёт кандидатов; LLM уточняет | Да (уточняет) |
| `required_input_fields`, `output_fields`, `feature_tables`, `validation_rules` | структура секции | `MetadataExtractor`; LLM — для doc_type-специфичных полей, которых нет в структуре | Частично |
| поля типа карточки (`task_inputs`, `compatible_models`, `metrics` и т. п.) | содержимое секции | LLM | Да |
| `confidence_level` | уверенность классификации, content-confidence LLM, precheck, попытки | `ConfidenceCalculator` | Нет (LLM даёт только вход) |
| `classifier_path`, `classifier_tree_version` | путь классификации, версия дерева | `ClassificationMetadataResolver` | Нет |
| `phase`, `retrieval_purpose` чанка | metadata карточки (из хинтов) | Chunking (SETUP-08) | Нет |

Значения хинтов проходят ту же проверку по онтологии, что и любые другие: при сохранении узла дерева, при генерации карточки (`OntologyMapper`) и в SETUP-07.

---

## 7. Сериализация (YAML front matter)

### 7.1. Формат

Карточка хранится как Markdown-файл с YAML front matter в блоке `---`. Ключи front matter — snake_case. Список-значения могут быть записаны в block style или flow style.

Путь хранения артефакта: `rag/cards/{setup_job_id}/{doc_id}.md`.

### 7.2. Примеры YAML front matter для всех 7 doc_types

#### Пример: analytics_card

```yaml
---
doc_id: analytics.sensor_analytics_T.v1
doc_type: analytics_card
title: Sensor analytics feature table
version: "1.0"
status: generated
source_files: [analytics.md]
source_sections: [sec_005]
domain: [naval]
task_type: [classification, ranking]
data_source: [radar, tracks_fused]
entity_type: [sensor]
phase: [feature_synthesis, validation]
agent_targets: [FeatureSynthesisAgent, FeatureCriticAgent]
retrieval_tags: [sensor, analytics, uptime, detection_probability]
feature_tables:
  - table_id: sensor_feature_table
    columns: [sensor_id, uptime, detection_probability, scan_rate, rcs_mean]
output_fields: [uptime, detection_probability]
confidence_level: medium
metadata_schema_version: rag_metadata_v1
---
```

#### Пример: schema_card

```yaml
---
doc_id: schema.radar_track_schema.v1
doc_type: schema_card
title: Radar track data schema
version: "1.0"
status: ready_for_metadata_validation
source_files: [data_description.md]
source_sections: [sec_001, sec_002]
domain: [naval]
task_type: [classification, trajectory_forecasting]
data_source: [radar]
entity_type: [track]
phase: [data_profiling, feature_synthesis]
agent_targets: [DataProfilingAgent, FeatureSynthesisAgent, DomainContextAgent]
retrieval_tags: [radar, track, schema, fields, data_structure]
feature_tables:
  - table_id: radar_track_table
    columns: [track_id, timestamp, lat, lon, speed, course, rcs, source_sensor]
required_input_fields: [track_id, timestamp, lat, lon]
output_fields: [track_id, timestamp, lat, lon, speed, course, rcs, source_sensor]
confidence_level: high
metadata_schema_version: rag_metadata_v1
---
```

#### Пример: task_card

```yaml
---
doc_id: task.surface_threat_classification.v1
doc_type: task_card
title: Surface threat classification task
version: "1.0"
status: ready_for_metadata_validation
source_files: [ml_task_spec.md]
source_sections: [sec_010]
domain: [naval]
task_type: [classification]
data_source: [radar, tracks_fused, AIS]
entity_type: [vessel, track]
phase: [task_discovery, feature_synthesis, model_selection]
agent_targets: [TaskDiscoveryAgent, FeatureSynthesisAgent, ModelSelectionAgent]
retrieval_tags: [classification, threat, surface, vessel, radar, binary]
compatible_models: [RandomForestClassifier, GradientBoostingClassifier, LogisticRegression]
confidence_level: high
metadata_schema_version: rag_metadata_v1
---
```

#### Пример: field_definition_card

```yaml
---
doc_id: field.radar_cross_section.v1
doc_type: field_definition_card
title: Radar cross section (RCS) field definition
version: "1.0"
status: generated
source_files: [data_description.md]
source_sections: [sec_003]
domain: [naval, air]
task_type: [classification, object_detection]
data_source: [radar]
entity_type: [track, vessel, aircraft]
phase: [data_profiling, feature_synthesis]
agent_targets: [DataProfilingAgent, FeatureSynthesisAgent]
retrieval_tags: [rcs, radar_cross_section, field, unit, dBsm]
required_input_fields: [rcs]
output_fields: [rcs]
confidence_level: high
metadata_schema_version: rag_metadata_v1
---
```

#### Пример: feature_pattern_card

```yaml
---
doc_id: feature.track_speed_delta.v1
doc_type: feature_pattern_card
title: Track speed change (delta speed)
version: "1.0"
status: ready_for_metadata_validation
source_files: [feature_engineering_guide.md]
source_sections: [sec_015]
domain: [naval]
task_type: [classification, trajectory_forecasting, anomaly_detection]
data_source: [radar, tracks_fused]
entity_type: [track, vessel]
phase: [feature_synthesis]
agent_targets: [FeatureSynthesisAgent, FeatureCriticAgent]
retrieval_tags: [speed, delta, temporal, manoeuvre, track, feature]
required_input_fields: [track_id, timestamp, speed]
output_fields: [speed_delta_1min, speed_delta_5min]
confidence_level: high
metadata_schema_version: rag_metadata_v1
---
```

#### Пример: validation_rule_card

```yaml
---
doc_id: validation.speed_range_check.v1
doc_type: validation_rule_card
title: Vessel speed range validation rule
version: "1.0"
status: generated
source_files: [data_quality_rules.md]
source_sections: [sec_021]
domain: [naval]
task_type: [classification]
data_source: [radar, AIS]
entity_type: [vessel, track]
phase: [validation, data_profiling]
agent_targets: [FeatureCriticAgent, DataProfilingAgent]
retrieval_tags: [validation, speed, range, vessel, quality, rule]
validation_rules:
  - rule_id: speed_non_negative
    condition: speed >= 0
    severity: error
  - rule_id: speed_max_realistic
    condition: speed <= 50
    severity: warning
required_input_fields: [track_id, speed]
confidence_level: high
metadata_schema_version: rag_metadata_v1
---
```

#### Пример: question_template_card

```yaml
---
doc_id: question.missing_target_variable.v1
doc_type: question_template_card
title: Missing target variable clarification template
version: "1.0"
status: generated
source_files: [dialogue_templates.md]
source_sections: [sec_030]
domain: [naval, analytical]
task_type: [classification, regression]
entity_type: [track, vessel]
phase: [task_discovery, nlu]
agent_targets: [TaskDiscoveryAgent, DialogueOrchestratorAgent, NLUAgent]
retrieval_tags: [question, template, target, variable, clarification, dialogue]
required_input_fields: [task_type]
confidence_level: high
metadata_schema_version: rag_metadata_v1
---
```

---

## 8. Связь с DTO

| DTO | Роль |
| --- | --- |
| **DTO-61 `RAGCardMetadataDTO`** | Реализация данной схемы. Поле `front_matter` содержит все поля §3 и §4. Поле `metadata_schema_version = "rag_metadata_v1"` проставляется обязательно. Реализация: `schemas/setup/rag_card_metadata.py`. |
| **DTO-62 `RAGCardMarkdownDTO`** | Markdown-файл карточки: `front_matter_yaml` (сериализованный YAML из DTO-61) + `body_markdown` + итоговый `markdown`. Хранится в Object Storage. |
| **DTO-65 `CardValidationReportDTO`** | Отчёт проверки metadata против данной схемы. Поля: `passed: bool`, `errors: list`, `warnings: list`. Создаётся `CardValidationPrecheck` (SETUP-05) и SETUP-07 Metadata Validation Service. |
| **DTO-66 `RAGCardDTO`** | Основная карточка. Содержит `doc_id`, `doc_type`, `status`, `confidence_level`, ссылку на `markdown_artifact_id` (DTO-62) и на `RAGCardMetadataDTO` (DTO-61). |

Полный каталог DTO: [docs/03-architecture/services/data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md).

---

## 9. Политика миграции схемы

### 9.1. Текущая версия: `rag_metadata_v1`

Все карточки, сгенерированные SETUP-05 v1, имеют `metadata_schema_version = "rag_metadata_v1"`.

### 9.2. Bump `rag_metadata_v1` → `rag_metadata_v2`

1. Определить список breaking changes (изменение обязательных полей, переименование, удаление).
2. Создать ADR (через solution-architect) с обоснованием bump.
3. Обновить `metadata_schema_version` в конфигурации RAG Card Generator на `"rag_metadata_v2"`.
4. Обновить `CardValidationPrecheck` и SETUP-07 Validation Service: поддержать оба варианта (`v1` и `v2`) через стратегию по версии.
5. Старые карточки `v1` остаются валидными и не ломаются автоматически.
6. Новые карточки генерируются с `v2`.
7. Для перехода old-карточек на `v2` — отдельный migration job с повторной валидацией SETUP-07.
8. Обновить `rag/ontology/ontology_v1.yaml` при изменении enum, если изменение enum является частью breaking change.

### 9.3. Backward-compatible изменения (без bump)

- Добавление нового опционального поля в §4.
- Добавление нового `doc_type` в ontology (не меняет обязательность существующих полей).
- Добавление нового значения в enum `domain`, `task_type`, `data_source`, `entity_type`, `phase`, `agent_targets`.

---

## 10. Исторические обязательные поля (до SETUP-05)

До введения SETUP-05 metadata-схема определяла минимальный набор полей для карточек, создававшихся вручную или через legacy pipeline. Эти поля остаются валидными и включены в `rag_metadata_v1`:

```yaml
doc_id: feature_pattern.signal_quality.v1
doc_type: feature_pattern_card
title: "Signal Quality"
phase: [feature_synthesis, data_generation]
domain: [naval]
data_source: [radar]
task_type: [classification]
feature_family: signal_quality       # опциональное поле legacy; не обязательно в v1
retrieval_tags: [snr, signal_quality, radar, dB]
input_features: [snr]                # опциональное поле legacy; эквивалент required_input_fields
output_features: [signal_quality]    # опциональное поле legacy; эквивалент output_fields
confidence_level: high
version: "1.0"
owner: ml_knowledge_team
last_updated_at: 2026-05-18T00:00:00Z
metadata_schema_version: rag_metadata_v1
```

Поля `feature_family`, `input_features`, `output_features`, `unit`, `requires_temporal_sequence`, `supersedes`, `deprecated` — опциональные поля legacy и полностью совместимы с `rag_metadata_v1`. Они могут использоваться наряду с полями §4.

Если `requires_temporal_sequence: true`, то среди `input_features` (или `required_input_fields`) обязаны быть `timestamp` и `entity_id` (или их эквиваленты). Это требование форсит `validators/rag_metadata_validator.py`.

---

## Связанные документы

- [ontology.md](ontology.md) — canonical enum values.
- [document-types.md](document-types.md) — описание всех 13 типов RAG-карточек.
- [chunk-schema.md](chunk-schema.md) — схема chunk с chunk-metadata и `embedding_text`.
- [rag-lifecycle.md](rag-lifecycle.md) — статусы карточек и правила versioning.
- [rag-quality.md](rag-quality.md) — пороги quality gate.
- [retrieval-policies.md](retrieval-policies.md) — как metadata используется при retrieval.
- [rag/ontology/ontology_v1.yaml](../../rag/ontology/ontology_v1.yaml) — machine-readable ontology.
- [schemas/setup/rag_card_metadata.py](../../schemas/setup/rag_card_metadata.py) — Pydantic-реализация DTO-61.
- [validators/rag_metadata_validator.py](../../validators/rag_metadata_validator.py) — валидатор обязательных полей.
- [docs/02-system/features/SETUP-05-rag-cards-generation.md](../02-system/features/SETUP-05-rag-cards-generation.md) — полная спецификация SETUP-05.
