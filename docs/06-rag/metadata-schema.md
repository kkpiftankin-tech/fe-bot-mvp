# Metadata-схема RAG-карточки

Все RAG-карточки хранятся в YAML (front-matter) + Markdown (тело). Эта страница нормативна: каждый ключ обязателен или явно опционален.

## Обязательные поля

```yaml
doc_id: feature_pattern.signal_quality.v1     # стабильный, уникальный
doc_type: feature_pattern_card                 # один из document-types.md
title: "Signal Quality"                        # человекочитаемое название
phase:                                         # одна или несколько фаз
  - feature_synthesis
  - data_generation
domain:                                        # одно или несколько значений ontology.domain
  - naval
data_source:                                   # одно или несколько значений ontology.data_source
  - radar
task_type:                                     # одно или несколько значений ontology.task_type
  - classification
retrieval_tags:                                # свободные теги; используются для rerank
  - signal_quality
  - snr
  - dB
confidence_level: high                         # high | medium | low
version: "1.0"                                 # SemVer
owner: "ml_knowledge_team"                     # команда / человек
last_updated_at: 2026-05-18T00:00:00Z
```

## Опциональные поля

```yaml
feature_family: signal_quality                 # ontology.feature_family
requires_temporal_sequence: false              # bool; если true — temporal_importance обязателен
input_features:                                # для feature_pattern_card
  - snr
output_features:
  - signal_quality
unit: "dB"                                     # единицы измерения, если применимо
language: ru                                   # язык тела
deprecated: false
supersedes: feature_pattern.signal_quality.v0  # если новая версия заменяет старую
```

## Валидация

`validators/rag_metadata_validator.py` форсит:

- Все обязательные поля присутствуют.
- Значения `domain`, `data_source`, `task_type`, `doc_type`, `phase`, `confidence_level`, `feature_family` принадлежат онтологии.
- `doc_id` уникален в `rag/cards/`.
- `version` — валидный SemVer.
- `requires_temporal_sequence=true` → среди `input_features` обязаны быть `timestamp` и `entity_id` (или эквиваленты).
- `evidence_doc_ids` (для карточек с явной зависимостью от других) разрешаются.

## Пример карточки

```yaml
---
doc_id: feature_pattern.signal_quality.v1
doc_type: feature_pattern_card
title: "Signal Quality"
phase: [feature_synthesis, data_generation]
domain: [naval]
data_source: [radar]
task_type: [classification]
feature_family: signal_quality
retrieval_tags: [snr, signal quality, radar, dB]
input_features: [snr]
output_features: [signal_quality]
unit: "dB"
requires_temporal_sequence: false
confidence_level: high
version: "1.0"
owner: ml_knowledge_team
last_updated_at: 2026-05-18T00:00:00Z
---

# Signal Quality

Нормализованное качество сигнала, производное от SNR.

## Формула

signal_quality = snr / 20.0

## Применение

Используется как derived-признак классификации морских целей по РЛС.
Требует валидного `snr`. Шкала калибруется под радар; см. `analytics_card.sensor_analytics_T`.
```

## Связанные документы

- [ontology.md](ontology.md)
- [document-types.md](document-types.md)
- [chunk-schema.md](chunk-schema.md)
- [../../validators/rag_metadata_validator.py](../../validators/rag_metadata_validator.py)
