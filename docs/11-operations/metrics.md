# Метрики

## Соглашения

- Формат: Prometheus exposition (`/metrics`).
- Префикс: `fe_bot_`.
- Labels: `service`, `agent_name`, `phase`, `kb_version`, `conversation_id` (для high-cardinality эмитятся осторожно: см. note).

## HTTP / приложение

| Метрика | Тип | Labels | Назначение |
| --- | --- | --- | --- |
| `fe_bot_requests_total` | counter | route, status_code | трафик API |
| `fe_bot_request_latency_seconds` | histogram | route | latency API |

## Агенты

| Метрика | Тип | Labels | Назначение |
| --- | --- | --- | --- |
| `fe_bot_agent_runs_total` | counter | agent_name, phase, decision | сколько раз вызвался |
| `fe_bot_agent_latency_ms` | histogram | agent_name | latency агента |
| `fe_bot_llm_invalid_json_total` | counter | agent_name | сколько раз вернул невалидный JSON |
| `fe_bot_repair_loop_count` | histogram | agent_name | distribution repair-попыток |
| `fe_bot_need_more_context_total` | counter | agent_name, phase | сколько раз агент попросил уточнить |

## RAG

| Метрика | Тип | Labels | Назначение |
| --- | --- | --- | --- |
| `fe_bot_rag_retrieval_total` | counter | agent_name, phase | вызовы retrieval |
| `fe_bot_rag_retrieval_latency_ms` | histogram | agent_name | latency retrieval |
| `fe_bot_rag_topk_hit_rate` | gauge | doc_type | оценка hit-rate из eval |
| `fe_bot_rag_no_context_total` | counter | phase | случаи 0 hits |

## Setup

| Метрика | Тип | Labels | Назначение |
| --- | --- | --- | --- |
| `fe_bot_setup_phase_total` | counter | phase, outcome | по фазам Setup-мастера |
| `fe_bot_setup_phase_latency_seconds` | histogram | phase | latency фазы |
| `fe_bot_kb_published_total` | counter | — | публикации KB |

## Data / Export

| Метрика | Тип | Labels | Назначение |
| --- | --- | --- | --- |
| `fe_bot_generated_datasets_total` | counter | task_type, outcome | сгенерированные датасеты |
| `fe_bot_export_success_total` | counter | — | успешные экспорты |
| `fe_bot_validation_failures_total` | counter | validator_name | сбои валидаторов |
| `fe_bot_artifact_download_total` | counter | kind | скачивания |

## High-cardinality

`conversation_id` не используется как label в Prometheus. Эти разрезы — в audit log / Analytics dashboards.

## Связанные документы

- [observability.md](observability.md)
- [runbook.md](runbook.md)
- [../02-system/features/ANALYTICS-01-session-dashboard.md](../02-system/features/ANALYTICS-01-session-dashboard.md)
