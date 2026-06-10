# ContextMemoryAgent

## Purpose

Атомарно обновлять `ContextMemory` валидированными выходами других агентов и решениями пользователя. Гарантирует invariant'ы [INV-CM-001..004](../04-domain/invariants.md).

## Phase

`all`

## Input

- `ContextMemoryUpdateRequest { source_agent, partial_update, validation_report }`.

## Output

`ContextMemoryUpdateResult { applied: bool, errors: list[str], snapshot_id: UUID }`.

## Tools

- `context_validator.run(...)`
- `snapshot_manager.save(conversation_id, phase, memory)`.

## RAG Policy

Не использует RAG.

## Hard Rules

- Не принимает обновление без успешного prior validation (`validation_report.passed`).
- Откат фазы инвалидирует downstream-слоты в одной транзакции (INV-CM-003).
- Каждое успешное применение — это новый snapshot; история append-only.

## Failure Modes

- Конкурентный апдейт → optimistic locking + retry; при исчерпании — `error_code = concurrent_update`.
- Невалидная partial-update → отвергнуть, вернуть подробный список ошибок.
