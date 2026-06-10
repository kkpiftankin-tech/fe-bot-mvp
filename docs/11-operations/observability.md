# Наблюдаемость

## Назначение

Зафиксировать, какие сигналы система обязана эмитить, чтобы отлаживать и измерять её работу.

## Структурированные логи

Каждая строка лога — JSON c набором полей-якорей:

```json
{
  "ts": "2026-05-18T00:00:00Z",
  "level": "INFO",
  "service": "agent_runtime",
  "conversation_id": "conv_001",
  "kb_version": "kb_2026_05_18_v1",
  "phase": "feature_synthesis",
  "agent_name": "FeatureSynthesisAgent",
  "node_name": "feature_synthesis",
  "trace_id": "abc...",
  "prompt_template_version": "feature_synthesis@1.2",
  "llm_model": "llama3.2:latest",
  "llm_latency_ms": 412,
  "validation_status": "passed",
  "repair_loop_count": 1,
  "msg": "agent_run_finished"
}
```

## Трейсинг

OpenTelemetry-стиль. Span на:

- HTTP-запрос (`/api/chat`, `/setup/*`).
- LangGraph-узел.
- LLM-вызов.
- RAG retrieval.
- Validator.
- DB / MinIO операцию.

## Audit log

Отдельно от ops-логов. Append-only, см. [`AuditChain`](../04-domain/entities.md) и [ANALYTICS-09](../02-system/features/ANALYTICS-09-audit-trail.md).

## Хранилища сигналов

| Сигнал | Где |
| --- | --- |
| Логи | stdout → агрегатор по выбору (Loki / ELK / Datadog) |
| Метрики | Prometheus scrape `/metrics` |
| Трейсы | OTLP-export в Jaeger / Tempo (опц.) |
| Audit | PostgreSQL (append-only) |

## Связанные документы

- [metrics.md](metrics.md)
- [runbook.md](runbook.md)
- [../02-system/non-functional-requirements.md](../02-system/non-functional-requirements.md)
