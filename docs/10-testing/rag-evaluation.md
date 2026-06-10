# RAG evaluation

## Назначение

Доказать, что retrieval возвращает нужные карточки на curated-запросы — отдельно от ML-метрик и отдельно от LLM-качества.

## Eval-сьют

Файлы под [`tests/rag_eval/`](../../tests/rag_eval/) — YAML с парами `(query, expected_doc_ids)`. Один файл на семейство:

- `tests/rag_eval/feature_pattern_queries.yaml`
- `tests/rag_eval/domain_profile_queries.yaml`
- `tests/rag_eval/schema_card_queries.yaml`
- `tests/rag_eval/validation_rule_queries.yaml`
- `tests/rag_eval/model_recommendation_queries.yaml`

## Метрики

| Метрика | Целевой порог MVP |
| --- | --- |
| `recall@5` per семейство | ≥ 0.8 |
| `precision@5` per семейство | ≥ 0.5 |
| `no_context_rate` (доля запросов с 0 hits) | ≤ 5 % |

## Когда прогоняется

- При публикации новой `kb_version` ([SETUP-10](../02-system/features/SETUP-10-retrieval-tests.md)).
- На CI — на каждом PR, изменяющем `rag/` или embedding-модель.

## Запуск

```bash
make test-rag
```
