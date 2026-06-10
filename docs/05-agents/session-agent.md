# SessionAgent

## Purpose

Создать или восстановить пользовательскую сессию Runtime: выпустить `conversation_id`, привязать его к активной `kb_version`, инициализировать пустую `ContextMemory`.

## Phase

`PHASE_0_INITIALIZATION`

## Input

- `SessionStartRequest { user_id? , kb_version? }`
- Активная `KnowledgeBaseVersion`.

## Output

`SessionStartResponse` — см. `schemas/agent_outputs.py`.

## Tools

- `session_service.create(...)`
- `kb_registry.get_active()`
- `context_memory.init(conversation_id, kb_version)`

## RAG Policy

Не использует RAG.

## Hard Rules

- Стартовать сессию запрещено, если нет активной `KnowledgeBaseVersion` — возвращать структурированную ошибку с указанием «нужен Setup».
- `kb_version`, заданная клиентом, обязана существовать; иначе — ошибка.
- Не модифицировать существующие сессии: создаются всегда новые, восстановление — отдельная операция.

## Failure Modes

- Нет активной KB → `error_code = no_active_kb`, ссылка на Setup-мастер.
- БД недоступна → retry через `LLM Gateway`-style backoff (200 мс / 1 с / 5 с), затем `error_code = persistence_unavailable`.
