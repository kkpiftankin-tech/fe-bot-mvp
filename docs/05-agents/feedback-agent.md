# FeedbackAgent

## Purpose

Обработать подтверждения, правки и откаты пользователя на любой фазе: confirm features, override model, add/remove field, restart session.

## Phase

`all`

## Input

- `ParsedUserInput` с `intent ∈ {confirm_features, clarify_feature, restart, ...}`.
- `ContextMemory`.

## Output

`FeedbackDecision { action, target, payload, route_back_to_phase? }`.

## Tools

- `context_memory_agent.apply_update(...)`.
- `langgraph.rollback_to(phase)`.

## RAG Policy

Не использует RAG.

## Hard Rules

- `restart` интент обязан создавать новую сессию, а не правит существующую.
- `rollback` обязан инвалидировать downstream-слоты (INV-CM-003).
- Каждое действие эмитит соответствующее audit event.

## Failure Modes

- Override без обоснования при критическом изменении (например, отклонение валидатора) → запросить обоснование, не применять без него.
