# DialogueOrchestratorAgent

## Purpose

Принимать решение о следующем действии: какого агента вызывать дальше, продвигать ли фазу, требовать ли уточнения у пользователя. **Реализация — LangGraph state machine, не LLM.**

## Phase

`all`

## Input

- `ParsedUserInput` (от NLUAgent).
- `ContextMemory`.
- `ValidationReport` предыдущего шага (если был).

## Output

`OrchestrationDecision { next_node, advance_phase?, repair_request?, clarification_prompt? }`.

## Tools

- LangGraph runtime (узлы, переходы, conditional routing).
- `phase_completion.check(current_phase, context_memory)`.

## RAG Policy

Не использует RAG напрямую.

## Hard Rules

- Никаких LLM-вызовов для маршрутизации.
- Условия переходов между фазами читаются строго из completion-criteria (см. [../09-langgraph/state-machine.md](../09-langgraph/state-machine.md)).
- Не пропускать фазу даже при «уверенном» вводе пользователя — каждая фаза имеет свой набор обязательных слотов.

## Failure Modes

- Получен невалидный `ParsedUserInput` → отказ от продвижения, эмиссия clarification.
- Repair-request от предыдущего шага → передать его соответствующему агенту, не продвигать фазу.
