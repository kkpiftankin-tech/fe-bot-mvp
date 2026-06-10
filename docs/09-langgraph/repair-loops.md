# Repair loops

## Принцип

Если узел произвёл невалидный output, runtime не падает и не сдвигается дальше. Он формирует `RepairRequest` (см. [../07-contracts/structured-outputs.md](../07-contracts/structured-outputs.md)) и переотправляет производящему узлу. Repair ограничен `max_retries`.

## Где включены repair-loops

| Узел-источник | Триггер repair | Что отправляется обратно |
| --- | --- | --- |
| `feature_synthesis` | `feature_critic.decision=failed` или `multicollinearity.severity=high` | `RepairRequest` с приложенным `ValidationReport` |
| `generation_spec` | `generation_spec_validator` отверг | `RepairRequest` с конкретными codes |
| `generation_spec` | `data_validation` отверг (data-stage) | `RepairRequest` через `data_validation → generation_spec` |
| любой LLM-узел | невалидный JSON | внутренний repair Structured-Output Caller-а |

## Параметры

- `max_retries` (per-узел): 3.
- Backoff между retry: 0 (это логическая retry, не сетевая).
- После исчерпания `max_retries` → `END_PHASE_FAILED`, пользователь видит структурированную ошибку и кнопку «вернуться в предыдущую фазу».

## Что repair-промпт сообщает агенту

```text
SYSTEM:
You previously returned an output that failed validation.
Fix EXACTLY the listed issues. Do not change anything else.

ORIGINAL_INPUT:
{...}

PREVIOUS_OUTPUT:
{...}

VALIDATION_REPORT:
{ "decision": "failed",
  "findings": [
    {"code": "FEAT_004_TEMPORAL_DISALLOWED", "target_id": "range_acceleration",
     "message": "temporal_importance=false; временной признак запрещён"}
  ]
}

OUTPUT_SCHEMA:
{...}
```

См. [../00-methodology/prompt-engineering-rules.md](../00-methodology/prompt-engineering-rules.md#repair-loops).

## Связанные документы

- [state-machine.md](state-machine.md)
- [edges.md](edges.md)
- [../07-contracts/validation-report.md](../07-contracts/validation-report.md)
- [../00-methodology/prompt-engineering-rules.md](../00-methodology/prompt-engineering-rules.md)
