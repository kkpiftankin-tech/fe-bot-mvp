# Схема чанков

Карточка дробится на чанки — единицы embedding-а и retrieval. Каждый чанк наследует metadata карточки и добавляет свою.

## Обязательные поля чанка

```yaml
chunk_id: feature_pattern.signal_quality.v1.formula    # стабильный
doc_id: feature_pattern.signal_quality.v1              # родительская карточка
chunk_type: formula                                    # см. список ниже
phase: feature_synthesis                               # из родительской карточки
slot: derived_features                                 # семантический слот в фазе
retrieval_purpose:                                     # одна или несколько целей retrieval
  - synthesize_features
  - explain_feature
canonical_feature: signal_quality                      # если относится к признаку
required_fields:
  - snr
embedding_text: |
  Signal quality feature for radar SNR. Normalize snr into signal_quality by snr / 20.0.
  Use as derived feature for naval radar target classification.
priority: 80                                           # 0..100; rerank-сигнал
```

## chunk_type

Закрытое множество:

```text
summary
definition
inputs
outputs
formula
validation_rules
examples
agent_usage
constraints
metadata_summary
```

## retrieval_purpose

Закрытое множество (используется для `retrieval_planner`):

```text
discover_task
profile_data
explain_field
explain_feature
synthesize_features
validate_feature
generate_data
recommend_model
clarify_intent
```

## Откуда берутся поля чанка

Чанк не классифицируется заново. Классификация секции выполняется один раз на шаге 3 (дерево [SETUP-13](../02-system/features/SETUP-13-classifier-library.md)); её результат — metadata-хинты узлов — превращается в metadata карточки (шаг 4), а чанк наследует её ([ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)). Цепочка: узел дерева → `resolved_hints` → metadata карточки → metadata чанка → retrieval-фильтр агента ([retrieval-policies.md](retrieval-policies.md)).

| Поле чанка | Источник | Статус |
| --- | --- | --- |
| `doc_id`, `doc_type`, `domain`, `task_type`, `data_source`, `entity_type`, `agent_targets`, `retrieval_tags` | наследуются от карточки (`card_metadata`) | по [SETUP-08 AC-04](../02-system/features/SETUP-08-chunking.md) чанк наследует `doc_type` и `version`; в коде `Chunk.metadata` — свободный `dict` (`doc_type` и др.), отдельных полей нет |
| `phase` | `phase` карточки (из `phase_hint` узла) | целевое; в схеме чанка скаляр, у карточки список — правило выбора не определено (ADR-HTC-10, вопрос 4) |
| `retrieval_purpose` | `retrieval_purpose_hint` узла, перенесённый в metadata карточки; для чанка уточняется по `chunk_type` | целевое; см. оговорку ниже |
| `chunk_type`, `chunk_id`, `embedding_text`, `priority` | детерминированное правило chunking | реализовано в SETUP-08 (типы `summary`, `definition`, `metadata_summary`) |
| `slot`, `canonical_feature`, `required_fields` | содержимое карточки (имя признака, входные поля) | правило не определено: хинты узла их не покрывают (ADR-HTC-10, вопрос 2) |

**Оговорка.** Эта страница требует от чанка `phase`, `slot`, `retrieval_purpose` и `canonical_feature`, а [SETUP-08](../02-system/features/SETUP-08-chunking.md) на сегодня описывает только три типа чанков и не задаёт эти поля; модель `Chunk` (`schemas/rag/chunk.py`) отдельных полей `phase`, `slot`, `retrieval_purpose`, `canonical_feature` не содержит. До реализации хинтов `phase` и `retrieval_purpose` чанка не заполняются детерминированным правилом; с хинтами они берутся из metadata карточки, а не из отдельной эвристики в chunking. Остальные поля остаются на проектирование SETUP-08.

## Связь с агентами

| Агент | Запрашивает chunks с retrieval_purpose |
| --- | --- |
| `TaskDiscoveryAgent` | `discover_task`, `clarify_intent` |
| `DataProfilingAgent` | `profile_data`, `explain_field`, `clarify_intent` |
| `DomainContextAgent` | `discover_task`, `explain_feature` |
| `FeatureSynthesisAgent` | `synthesize_features`, `explain_feature` |
| `FeatureCriticAgent` | `validate_feature` |
| `DataGenerationSpecAgent` | `synthesize_features`, `generate_data`, `validate_feature` |
| `ModelSelectionAgent` | `recommend_model` |

## chunk_manifest.jsonl

`SETUP-08` эмитит `rag/manifests/chunk_manifest.jsonl`: одна строка JSON на чанк, формат — поля выше плюс `card_metadata` (наследованная).

## Связанные документы

- [metadata-schema.md](metadata-schema.md)
- [retrieval-policies.md](retrieval-policies.md)
- [../02-system/features/SETUP-08-chunking.md](../02-system/features/SETUP-08-chunking.md)
