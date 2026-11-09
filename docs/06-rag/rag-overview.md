# RAG Overview

## Цель раздела

Зафиксировать дизайн RAG-слоя так, чтобы маленькая LLM работала надёжно: онтология, типы документов, metadata, чанки, retrieval-политики, формат `EvidencePack`, жизненный цикл, качество, безопасность и failure handling.

## Базовый тезис

RAG в FE-Bot — это не «vector similarity search». Это:

```text
metadata filtering + semantic search + ontology + workflow-aware retrieval
```

Без metadata-фильтров `vector similarity search` шумит: запрос «морская классификация» с равной вероятностью находит «классификация морских млекопитающих» и «классификация морских целей по РЛС». Metadata (`domain=naval`, `task_type=classification`, `data_source=radar`) превращает retrieval в почти-детерминированный.

Полное методологическое обоснование (зачем, в каких трёх режимах, как взаимодействует с агентами и ContextMemory) — в [rag-methodology.md](rag-methodology.md).

## Слои

```text
1. Ontology              — словарь концепций и их связей
2. Metadata              — фильтры на каждой карточке и чанке
3. Document types        — закрытое множество типов карточек
4. Chunk schema          — как карточка дробится на retrievable-единицы
5. Retrieval policies    — per-agent, per-phase правила + graph expansion
6. EvidencePack          — что попадает в промпт агента
7. Ingestion pipeline    — как docs становятся карточками (Setup-стадия)
8. Lifecycle             — статусы, версионирование, governance
9. Quality               — validation, evaluation, gates, observability
10. Failure modes        — что делать при сбоях
11. Security             — access, isolation, redaction
```

## Карта документов

### Нормативные контракты RAG-слоя

| Документ | Содержание |
| --- | --- |
| [ontology.md](ontology.md) | Закрытые словари: domain, data_source, task_type, feature_family, ... |
| [document-types.md](document-types.md) | Типы RAG-карточек и кто их потребляет |
| [metadata-schema.md](metadata-schema.md) | Обязательные и опциональные поля metadata |
| [chunk-schema.md](chunk-schema.md) | Структура chunk, retrieval_purpose, embedding_text |
| [retrieval-policies.md](retrieval-policies.md) | Per-agent retrieval policies, fallback, graph expansion |
| [evidence-pack.md](evidence-pack.md) | Формат пакета, передаваемого агенту |
| [ingestion-pipeline.md](ingestion-pipeline.md) | Setup-pipeline: raw → published KB |

### Кросс-функциональные правила

| Документ | Содержание |
| --- | --- |
| [end-to-end-example.md](end-to-end-example.md) | Сквозной пример: как состояние беседы FE-бота (этап × предметная область × подтема) определяет отбор чанков в контекст и какие классификаторы (этапный, доменный, иерархический) для этого нужны |
| [rag-methodology.md](rag-methodology.md) | Главный методологический манифест: три режима, принцип, роль RAG |
| [rag-lifecycle.md](rag-lifecycle.md) | Статусы карточек, версионирование, governance, deprecation |
| [rag-quality.md](rag-quality.md) | Validation, evaluation, quality gates, observability, acceptance criteria |
| [rag-failure-modes.md](rag-failure-modes.md) | Действия при сбоях (parse / validate / index / retrieve / agent) |
| [rag-security.md](rag-security.md) | Контроль доступа, изоляция KB, redaction |

## Карта семейств карточек по фазам

| Фаза | Используемые семейства карточек |
| --- | --- |
| `task_discovery` | `domain_profile`, `question_template`, `glossary`, `task_card` |
| `data_profiling` | `schema_card`, `field_definition_card`, `question_template`, `glossary` |
| `domain_context` | `domain_profile`, `analytics_card`, `validation_rule` |
| `feature_synthesis` | `feature_pattern`, `analytics_card`, `schema_card`, `field_definition_card`, `validation_rule`, `glossary` |
| `data_generation` | `feature_pattern`, `analytics_card`, `validation_rule` |
| `model_selection` | `model_recommendation_card`, `task_card`, `validation_rule_card` |
| `export` | (не использует RAG) |

## Три режима

1. **Setup RAG** — пользователь загружает документы, система формирует RAG-карточки и публикует KB (SETUP-01..SETUP-11).
2. **Runtime RAG** — агенты используют опубликованную KB во время диалога (RUNTIME-02..RUNTIME-12).
3. **Analytics RAG** — мониторинг качества retrieval, использования карточек, пробелов (ANALYTICS-02, ANALYTICS-04).

Подробнее — в [rag-methodology.md §3](rag-methodology.md#три-режима-rag).

## Минимальный RAG MVP

Для MVP достаточно следующего корпуса:

```text
ontology:
  core_ontology

schema cards:
  situation, external_conditions, tactical_object, sensor, tracks_fused

task cards:
  surface_threat_evaluation, radar_detection,
  sonar_target_classification, ew_waveform_classification

analytics cards:
  sensor_analytics_T, object_analytics_T,
  environment_analytics_T, comms_esm_analytics_T

validation cards:
  requires_evidence, requires_source_fields,
  requires_timestamp, no_unknown_fields

question templates:
  data_source, data_type, fields,
  temporal_importance, class_distribution
```

Минимальные объёмы по типам карточек — в [document-types.md §Минимальный объём для MVP](document-types.md#минимальный-объём-для-mvp).

## Связанные документы

- [rag-methodology.md](rag-methodology.md)
- [rag-lifecycle.md](rag-lifecycle.md)
- [rag-quality.md](rag-quality.md)
- [rag-failure-modes.md](rag-failure-modes.md)
- [rag-security.md](rag-security.md)
- [ontology.md](ontology.md)
- [document-types.md](document-types.md)
- [metadata-schema.md](metadata-schema.md)
- [chunk-schema.md](chunk-schema.md)
- [retrieval-policies.md](retrieval-policies.md)
- [evidence-pack.md](evidence-pack.md)
- [ingestion-pipeline.md](ingestion-pipeline.md)
- [../03-architecture/c4-component-rag-service.md](../03-architecture/c4-component-rag-service.md)
