# EvidencePack

## Назначение

Компактный, agent-scoped срез retrieval-результатов, передаваемый агенту вместо сырых RAG-карточек.

## Зачем

- Маленькая LLM (4k–8k токенов) не выдерживает «полные» карточки целиком.
- Без сегментации promo-агент получает информационный шум, рассуждение деградирует.
- `evidence_doc_ids`, цитируемые признаком, должны соответствовать `doc_id`-ам из этого пакета.

## Структура

```python
class EvidencePack(BaseModel):
    phase: Phase
    agent_name: str
    domain: str | None
    data_source: str | None
    task_type: TaskType | None

    items: list[EvidenceItem]


class EvidenceItem(BaseModel):
    doc_id: str
    chunk_id: str
    chunk_type: ChunkType
    slot: str
    snippet: str                  # ≤ 800 символов
    metadata_summary: dict        # сжатые metadata
    score: float
```

## Принципы сборки

1. **Group by doc_type.** Внутри пакета первичны типы карточек: `feature_pattern` отдельно от `analytics_card`. Это помогает агенту работать со слотами.
2. **Top-K per chunk_type.** Из каждого `chunk_type` берётся не более N (обычно 2–3) лучших; иначе один doctype вытесняет остальные.
3. **Snippet, не fulltext.** `snippet` — ≤ 800 символов оригинального тела чанка. Если длиннее — обрезается с многоточием.
4. **Metadata-summary.** Включает только то, что важно для рассуждения: `doc_type`, `confidence_level`, `feature_family`, `unit`, `requires_temporal_sequence`. Полная metadata в пакет не идёт.
5. **Полный набор `doc_id` сохраняется.** Агент обязан вернуть `evidence_doc_ids ⊆ items.doc_id`.

## Пример

```json
{
  "phase": "feature_synthesis",
  "agent_name": "FeatureSynthesisAgent",
  "domain": "naval",
  "data_source": "radar",
  "task_type": "classification",
  "items": [
    {
      "doc_id": "feature_pattern.signal_quality.v1",
      "chunk_id": "feature_pattern.signal_quality.v1.formula",
      "chunk_type": "formula",
      "slot": "derived_features",
      "snippet": "signal_quality = snr / 20.0. Используется как derived-признак классификации морских целей по РЛС.",
      "metadata_summary": {
        "doc_type": "feature_pattern_card",
        "confidence_level": "high",
        "feature_family": "signal_quality",
        "unit": "ratio",
        "requires_temporal_sequence": false
      },
      "score": 0.87
    },
    {
      "doc_id": "analytics_card.sensor_quality.v1",
      "chunk_id": "analytics_card.sensor_quality.v1.definition",
      "chunk_type": "definition",
      "slot": "domain_context",
      "snippet": "false_alarm_rate_T — доля ложных тревог за окно T. Высокий уровень ухудшает classification accuracy.",
      "metadata_summary": {
        "doc_type": "analytics_card",
        "confidence_level": "high",
        "feature_family": "sensor_analytics"
      },
      "score": 0.81
    }
  ]
}
```

## Бюджет

| Параметр | Дефолт |
| --- | --- |
| Макс. `items` в пакете | 12 |
| Макс. длина `snippet` | 800 символов |
| Макс. суммарный объём пакета | ~3000 токенов |
| Минимальный `score` | 0.6 после rerank |

## Связанные документы

- [retrieval-policies.md](retrieval-policies.md)
- [chunk-schema.md](chunk-schema.md)
- [../03-architecture/c4-component-rag-service.md](../03-architecture/c4-component-rag-service.md)
- [../03-architecture/c4-component-agent-runtime.md](../03-architecture/c4-component-agent-runtime.md)
