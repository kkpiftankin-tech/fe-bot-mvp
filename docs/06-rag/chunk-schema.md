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
