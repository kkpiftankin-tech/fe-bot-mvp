# AuditAgent

## Purpose

Append событий в `AuditChain`: source-uploads, card-reviewed, kb-published, agent-run, feature-confirmed, artifact-exported, artifact-downloaded и т. д. Поставщик данных для [ANALYTICS-09](../02-system/features/ANALYTICS-09-audit-trail.md).

## Phase

`all`

## Input

- `AuditEventRequest { kind, entity_id, parent_id?, payload }`.

## Output

`AuditNode` — см. `schemas/audit.py`.

## Tools

- `audit_service.append(node)`.
- `payload_hasher.sha256(payload)` для `payload_digest`.

## RAG Policy

Не использует RAG.

## Hard Rules

- Append-only. Никаких UPDATE / DELETE по существующим `AuditNode`.
- Редакция факта — это новое событие со ссылкой на корректируемый `audit_node_id`.
- `payload_digest` обязан быть детерминирован для одного и того же payload.

## Failure Modes

- БД временно недоступна → события буферизуются в локальный fallback (WAL-стиль) с обязательным flush до завершения шага оркестратора.
- Конфликт `audit_node_id` (теоретически невозможен при UUID v4) → retry с новым UUID; первая попытка остаётся в логах как «collision».
